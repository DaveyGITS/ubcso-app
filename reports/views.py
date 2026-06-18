from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django_ratelimit.decorators import ratelimit
from core.audit import log_action, AuditActions
from .models import AccomplishmentReport, ReportAttachment
from organizations.models import Organization
from organizations.constants import PUBLICLY_VISIBLE_STATUSES
from core.models import AcademicPeriod
import datetime

_MAX_DT = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)


def leaderboard_view(request):
    """Public leaderboard — visible to guests and students."""
    period_filter = request.GET.get('period', 'current')

    periods = AcademicPeriod.objects.all().order_by('-start_date')
    current_period = AcademicPeriod.objects.filter(is_current=True).first()

    # Build queryset — exclude CSO org and dissolved orgs
    orgs = Organization.objects.filter(is_active=True, is_cso=False, status__in=PUBLICLY_VISIBLE_STATUSES)

    if period_filter == 'current' and current_period:
        approved_filter = Q(
            accomplishment_reports__status='approved',
            accomplishment_reports__academic_period=current_period
        )
        report_filter = Q(status='approved', academic_period=current_period)
    else:
        # 'all' or no current period or specific period id
        if period_filter not in ('current', 'all'):
            try:
                selected_period = AcademicPeriod.objects.get(id=int(period_filter))
                approved_filter = Q(
                    accomplishment_reports__status='approved',
                    accomplishment_reports__academic_period=selected_period
                )
                report_filter = Q(status='approved', academic_period=selected_period)
            except (ValueError, AcademicPeriod.DoesNotExist):
                approved_filter = Q(accomplishment_reports__status='approved')
                report_filter = Q(status='approved')
        else:
            approved_filter = Q(accomplishment_reports__status='approved')
            report_filter = Q(status='approved')

    orgs = orgs.annotate(
        report_count=Count('accomplishment_reports', filter=approved_filter)
    ).order_by('-report_count', 'name')

    # Build a lookup: org_id -> timestamp when they reached their current count
    # i.e. the created_at of their Nth approved report (where N = report_count)
    org_ids = [org.id for org in orgs]
    reports_by_org = {}
    for report in (AccomplishmentReport.objects
                   .filter(report_filter, organization_id__in=org_ids)
                   .order_by('created_at')
                   .values('organization_id', 'created_at')):
        org_id = report['organization_id']
        reports_by_org.setdefault(org_id, []).append(report['created_at'])

    def nth_report_time(org):
        """Timestamp when org reached its current report_count (the Nth report)."""
        if org.report_count == 0:
            return None
        times = reports_by_org.get(org.id, [])
        if len(times) >= org.report_count:
            return times[org.report_count - 1]  # 0-indexed Nth entry
        return times[-1] if times else None

    # Sort: most reports first, then by when they reached that count (earliest wins), then name
    orgs_list = sorted(
        orgs,
        key=lambda o: (
            -o.report_count,
            nth_report_time(o) or _MAX_DT,
            o.name,
        )
    )

    # Assign ranks with dense ranking (1, 1, 2, 2, 3 — no gaps on ties)
    ranked = []
    current_rank = 0
    previous_count = None

    for org in orgs_list:
        if org.report_count != previous_count:
            current_rank += 1
        previous_count = org.report_count
        ranked.append({'org': org, 'rank': current_rank, 'report_count': org.report_count})

    return render(request, 'reports/leaderboard.html', {
        'ranked': ranked,
        'periods': periods,
        'current_period': current_period,
        'period_filter': period_filter,
    })


@login_required
@ratelimit(key='user', rate='10/d', method='POST', block=True)
def submit_report_view(request, org_id):
    """Chairman, co-chairman, or officer can submit a report."""
    from memberships.models import Membership
    org = get_object_or_404(Organization, id=org_id, is_active=True)

    if org.is_cso:
        messages.error(request, 'The CSO organization cannot submit accomplishment reports.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    membership = Membership.objects.filter(
        user=request.user,
        organization=org,
        status='active',
        organization__is_active=True,
        role__in=['chairman', 'co_chairman', 'officer']
    ).first()

    if not membership:
        messages.error(request, 'You do not have permission to submit reports for this organization.')
        return redirect('organizations:org_profile', org_id=org_id)

    current_period = AcademicPeriod.objects.filter(is_current=True).first()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        files = request.FILES.getlist('attachments')

        if not title or not description:
            messages.error(request, 'Title and description are required.')
            return render(request, 'reports/submit_report.html', {
                'org': org, 'current_period': current_period
            })

        # Validate file sizes (10MB max each)
        for f in files:
            if f.size > 10 * 1024 * 1024:
                messages.error(request, f'"{f.name}" exceeds the 10MB file size limit.')
                return render(request, 'reports/submit_report.html', {
                    'org': org, 'current_period': current_period
                })

        activity_name = request.POST.get('activity_name', '').strip()
        date_of_activity_str = request.POST.get('date_of_activity', '').strip()
        date_of_activity = None
        if date_of_activity_str:
            try:
                from datetime import date
                date_of_activity = date.fromisoformat(date_of_activity_str)
            except ValueError:
                pass
        academic_year = request.POST.get('academic_year', '').strip()
        semester = request.POST.get('semester', '').strip()

        report = AccomplishmentReport.objects.create(
            organization=org,
            submitted_by=request.user,
            academic_period=current_period,
            title=title,
            description=description,
            status='pending',
            activity_name=activity_name,
            date_of_activity=date_of_activity,
            academic_year=academic_year,
            semester=semester,
        )

        for f in files:
            ReportAttachment.objects.create(
                report=report,
                file=f,
                filename=f.name,
                filesize=f.size,
            )
        
        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.REPORT_SUBMITTED,
            target=org,
            details=f'Submitted accomplishment report: {title} for {org.name}',
            request=request
        )

        # Notify CSO admins
        from announcements.utils import send_notification
        from django.urls import reverse
        from accounts.models import User
        admins = list(User.objects.filter(
            Q(is_cso_admin=True) | Q(is_cso_president=True),
            is_active=True
        ))
        if admins:
            send_notification(
                title=f'New accomplishment report — {org.name}',
                message=f'{request.user.get_full_name()} submitted a report "{title}" from {org.name}.',
                recipients=admins,
                sender=request.user,
                organization=org,
                link_url=reverse('reports:admin_review_report', kwargs={'report_id': report.id}),
                notification_type='report',
            )

        messages.success(request, 'Report submitted successfully! The CSO admin will review it.')
        return redirect('reports:org_reports', org_id=org_id)

    return render(request, 'reports/submit_report.html', {
        'org': org,
        'current_period': current_period,
    })


@login_required
def org_reports_view(request, org_id):
    """View reports for an org — accessible to org members."""
    from memberships.models import Membership
    org = get_object_or_404(Organization, id=org_id, is_active=True)

    membership = Membership.objects.filter(
        user=request.user, organization=org, status='active', organization__is_active=True,
    ).first()

    is_leader = membership and membership.role in ['chairman', 'co_chairman', 'officer']
    is_admin = request.user.is_cso_admin or request.user.is_cso_president

    if not membership and not is_admin:
        messages.error(request, 'You must be a member to view reports.')
        return redirect('organizations:org_profile', org_id=org_id)

    reports = AccomplishmentReport.objects.filter(
        organization=org
    ).select_related('submitted_by', 'academic_period').prefetch_related('attachments')

    return render(request, 'reports/org_reports.html', {
        'org': org,
        'reports': reports,
        'membership': membership,
        'is_leader': is_leader,
        'is_admin': is_admin,
    })


@login_required
def report_archive_view(request, org_id):
    """Archive of all approved accomplishment reports for an org, filterable by academic year and semester."""
    from organizations.models import Organization
    from memberships.models import Membership
    from .models import ReportCompilation

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    is_cso_admin = request.user.is_cso_admin or request.user.is_cso_president
    user_membership = Membership.objects.filter(
        user=request.user, organization=org, status='active'
    ).first()
    if not user_membership and not is_cso_admin:
        messages.error(request, 'You must be a member of this organization to view the archive.')
        return redirect('organizations:org_profile', org_id=org_id)

    academic_year_filter = request.GET.get('academic_year', '').strip()
    semester_filter = request.GET.get('semester', '').strip()

    reports_qs = AccomplishmentReport.objects.filter(
        organization=org, status='approved'
    ).order_by('-created_at')

    if academic_year_filter:
        reports_qs = reports_qs.filter(academic_year=academic_year_filter)
    if semester_filter:
        reports_qs = reports_qs.filter(semester=semester_filter)

    academic_years = (AccomplishmentReport.objects
                      .filter(organization=org, status='approved')
                      .exclude(academic_year='')
                      .values_list('academic_year', flat=True)
                      .distinct()
                      .order_by('-academic_year'))

    is_chairman = user_membership and user_membership.role in ('chairman', 'co_chairman')
    compilations = ReportCompilation.objects.filter(organization=org) if is_chairman else []

    return render(request, 'reports/report_archive.html', {
        'org': org,
        'reports': reports_qs,
        'academic_year_filter': academic_year_filter,
        'semester_filter': semester_filter,
        'academic_years': academic_years,
        'is_chairman': is_chairman,
        'compilations': compilations,
    })


@login_required
@login_required
def report_compilation_create_view(request, org_id):
    """Chairman: create a named compilation from selected approved reports."""
    from organizations.models import Organization
    from memberships.models import Membership
    from .models import ReportCompilation

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    membership = Membership.objects.filter(
        user=request.user, organization=org, status='active',
        role__in=['chairman', 'co_chairman']
    ).first()
    if not membership:
        messages.error(request, 'Only the chairman can create report compilations.')
        return redirect('reports:report_archive', org_id=org_id)

    if request.method == 'POST':
        name = request.POST.get('compilation_name', '').strip()
        report_ids = request.POST.getlist('report_ids')
        if not name:
            messages.error(request, 'Compilation name is required.')
        elif not report_ids:
            messages.error(request, 'Select at least one report.')
        else:
            compilation = ReportCompilation.objects.create(
                organization=org, name=name, created_by=request.user
            )
            selected = AccomplishmentReport.objects.filter(
                id__in=report_ids, organization=org, status='approved'
            )
            compilation.reports.set(selected)
            messages.success(request, f'Compilation "{name}" created with {selected.count()} report(s).')

    return redirect('reports:report_archive', org_id=org_id)


@login_required
def report_compilation_list_view(request, org_id):
    """Chairman: list all report compilations for an org."""
    from organizations.models import Organization
    from memberships.models import Membership
    from .models import ReportCompilation

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    membership = Membership.objects.filter(
        user=request.user, organization=org, status='active',
        role__in=['chairman', 'co_chairman']
    ).first()
    if not membership:
        messages.error(request, 'Only the chairman can view report compilations.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    compilations = ReportCompilation.objects.filter(organization=org).prefetch_related('reports')
    return render(request, 'reports/compilations.html', {
        'org': org,
        'compilations': compilations,
    })


@login_required
def report_compilation_edit_view(request, org_id, compilation_id):
    """Chairman: edit a report compilation (name and reports)."""
    from organizations.models import Organization
    from memberships.models import Membership
    from .models import ReportCompilation

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    compilation = get_object_or_404(ReportCompilation, id=compilation_id, organization=org)
    
    membership = Membership.objects.filter(
        user=request.user, organization=org, status='active',
        role__in=['chairman', 'co_chairman']
    ).first()
    if not membership:
        messages.error(request, 'Only the chairman can edit compilations.')
        return redirect('reports:report_compilation_list', org_id=org_id)

    # Get all approved reports for this org
    approved_reports = AccomplishmentReport.objects.filter(
        organization=org, status='approved'
    ).order_by('-created_at')

    if request.method == 'POST':
        name = request.POST.get('compilation_name', '').strip()
        report_ids = request.POST.getlist('report_ids')
        
        if not name:
            messages.error(request, 'Compilation name is required.')
        elif not report_ids:
            messages.error(request, 'Select at least one report.')
        else:
            compilation.name = name
            compilation.save()
            
            # Update reports
            selected = AccomplishmentReport.objects.filter(
                id__in=report_ids, organization=org, status='approved'
            )
            compilation.reports.set(selected)
            
            messages.success(request, f'Compilation "{name}" updated with {selected.count()} report(s).')
            return redirect('reports:report_compilation_list', org_id=org_id)

    return render(request, 'reports/compilation_edit.html', {
        'org': org,
        'compilation': compilation,
        'approved_reports': approved_reports,
    })


@login_required
def report_compilation_delete_view(request, org_id, compilation_id):
    """Chairman: delete a report compilation."""
    from organizations.models import Organization
    from memberships.models import Membership
    from .models import ReportCompilation

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    compilation = get_object_or_404(ReportCompilation, id=compilation_id, organization=org)
    
    membership = Membership.objects.filter(
        user=request.user, organization=org, status='active',
        role__in=['chairman', 'co_chairman']
    ).first()
    if not membership:
        messages.error(request, 'Only the chairman can delete compilations.')
        return redirect('reports:report_compilation_list', org_id=org_id)

    if request.method == 'POST':
        compilation_name = compilation.name
        compilation.delete()
        messages.success(request, f'Compilation "{compilation_name}" deleted.')
        return redirect('reports:report_compilation_list', org_id=org_id)

    return render(request, 'reports/compilation_delete_confirm.html', {
        'org': org,
        'compilation': compilation,
    })


# ─── Admin views ─────────────────────────────────────────────────────────────

def admin_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_cso_admin and not request.user.is_cso_president:
            messages.error(request, 'Access denied.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def admin_reports_view(request):
    """CSO admin sees all pending reports."""
    status_filter = request.GET.get('status', 'pending')
    reports = AccomplishmentReport.objects.filter(
        status=status_filter
    ).select_related('organization', 'submitted_by', 'academic_period').prefetch_related('attachments')

    pending_count = AccomplishmentReport.objects.filter(status='pending').count()

    return render(request, 'reports/admin_reports.html', {
        'reports': reports,
        'status_filter': status_filter,
        'pending_count': pending_count,
    })


@admin_required
@ratelimit(key='user', rate='20/h', method='POST', block=True)
def admin_review_report_view(request, report_id):
    """CSO admin approves or rejects a report."""
    from django.utils import timezone
    report = get_object_or_404(AccomplishmentReport, id=report_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            report.status = 'approved'
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.save()
            
            # Audit log
            log_action(
                actor=request.user,
                action=AuditActions.REPORT_APPROVED,
                target=report,
                details=f'Approved report: {report.title} from {report.organization.name}',
                request=request
            )
            
            from announcements.utils import send_notification
            from django.urls import reverse
            send_notification(
                title=f'Report approved — {report.organization.name}',
                message=f'Your accomplishment report "{report.title}" has been approved.',
                recipients=[report.submitted_by],
                sender=request.user,
                organization=report.organization,
                link_url=reverse('reports:org_reports', kwargs={'org_id': report.organization.id}),
                notification_type='report',
            )
            messages.success(request, f'Report "{report.title}" approved.')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '').strip()
            report.status = 'rejected'
            report.rejection_reason = reason
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.save()
            
            # Audit log
            log_action(
                actor=request.user,
                action=AuditActions.REPORT_REJECTED,
                target=report,
                details=f'Rejected report: {report.title} from {report.organization.name}. Reason: {reason}',
                request=request
            )
            
            from announcements.utils import send_notification
            from django.urls import reverse
            msg = f'Your accomplishment report "{report.title}" was not approved.'
            if reason:
                msg += f' Reason: {reason}'
            send_notification(
                title=f'Report rejected — {report.organization.name}',
                message=msg,
                recipients=[report.submitted_by],
                sender=request.user,
                organization=report.organization,
                link_url=reverse('reports:org_reports', kwargs={'org_id': report.organization.id}),
                notification_type='report',
            )
            messages.success(request, f'Report "{report.title}" rejected.')

    return redirect('reports:admin_reports')
