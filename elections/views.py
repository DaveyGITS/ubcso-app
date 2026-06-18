from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Election, ElectionPosition, ElectionVoter, Candidate, Vote
from .utils import is_election_manager, compute_voter_pool, get_vote_tally, get_voter_pool_description
from .forms import ElectionForm, ElectionPositionForm, VoterPoolForm
from core.enforcement import enforce_election_schedule, close_overdue_elections
from organizations.constants import PUBLICLY_VISIBLE_STATUSES


# ─── Time-based enforcement (Celery-independent) ──────────────────────────────
# enforce_election_schedule and close_overdue_elections are imported from core.enforcement


# ─── Election List ────────────────────────────────────────────────────────────

@login_required
def election_list_view(request):
    from memberships.models import Membership
    from organizations.models import Organization

    # Enforce time-based close on all open elections before rendering the list
    close_overdue_elections()
    from core.enforcement import open_scheduled_elections
    open_scheduled_elections()

    # Elections the user manages — strictly org chairman/co-chairman only
    managed_org_ids = Membership.objects.filter(
        user=request.user,
        status='active',
        role__in=['chairman', 'co_chairman'],
    ).values_list('organization_id', flat=True)

    managed_elections = Election.objects.filter(
        organization_id__in=managed_org_ids
    ).select_related('organization').order_by('-created_at')

    # Elections the user can vote in — exclude ones they manage to avoid duplication
    managed_election_ids = managed_elections.values_list('id', flat=True)
    voter_elections = Election.objects.filter(
        voters__user=request.user,
        status__in=['open', 'results_released'],
    ).exclude(
        id__in=managed_election_ids
    ).select_related('organization').order_by('-created_at')

    # CSO admin/president oversight — all elections system-wide (read-only view)
    is_cso_admin = request.user.is_cso_admin or request.user.is_cso_president
    oversight_elections = None
    if is_cso_admin:
        oversight_elections = Election.objects.exclude(
            id__in=managed_election_ids
        ).select_related('organization').order_by('-created_at')

    # User can create if they manage any org (checked by eligible_orgs in create view)
    # We check if they have any chairman/co_chairman membership, not whether elections exist
    can_create = managed_org_ids.exists()

    return render(request, 'elections/list.html', {
        'managed_elections': managed_elections,
        'voter_elections': voter_elections,
        'oversight_elections': oversight_elections,
        'is_cso_admin': is_cso_admin,
        'can_create': can_create,
        'now': timezone.now(),
    })


# ─── Create Election ──────────────────────────────────────────────────────────

@login_required
def election_create_view(request):
    from memberships.models import Membership
    from organizations.models import Organization

    # Only orgs where user is chairman or co-chairman
    managed_org_ids = Membership.objects.filter(
        user=request.user,
        status='active',
        role__in=['chairman', 'co_chairman'],
    ).values_list('organization_id', flat=True)
    eligible_orgs = Organization.objects.filter(
        id__in=managed_org_ids,
        is_active=True,
        status__in=PUBLICLY_VISIBLE_STATUSES,
    )

    if not eligible_orgs.exists():
        messages.error(request, 'You do not manage any organizations.')
        return redirect('elections:election_list')

    from core.models import AcademicPeriod
    academic_periods = AcademicPeriod.objects.order_by('-start_date')

    if request.method == 'POST':
        form = ElectionForm(request.POST)
        org_id = request.POST.get('organization')
        org = get_object_or_404(Organization, id=org_id, is_active=True)

        if not is_election_manager(request.user, org):
            return HttpResponseForbidden('You do not have permission to manage this election.')

        if form.is_valid():
            election = form.save(commit=False)
            election.organization = org
            election.created_by = request.user
            election.status = 'draft'
            election.save()
            form.save_m2m()
            messages.success(request, f'Election "{election.title}" created.')
            return redirect('elections:election_manage', election_id=election.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = ElectionForm()

    return render(request, 'elections/create.html', {
        'form': form,
        'eligible_orgs': eligible_orgs,
        'academic_periods': academic_periods,
    })


# ─── Manage Election ──────────────────────────────────────────────────────────

@login_required
def election_action_buttons_view(request, election_id):
    """Lightweight endpoint that returns just the action buttons partial — used for HTMX refresh."""
    election = get_object_or_404(Election, id=election_id)
    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden()
    pool_preview_count = compute_voter_pool(election).count()
    return render(request, 'elections/_action_buttons_partial.html', {
        'election': election,
        'voter_pool_configured': pool_preview_count > 0,
        'is_voter': ElectionVoter.objects.filter(election=election, user=request.user).exists(),
    })


@login_required
def election_manage_view(request, election_id):
    from organizations.models import Organization
    from accounts.models import User

    election = get_object_or_404(Election, id=election_id)

    # Enforce time-based open/close regardless of Celery
    election = enforce_election_schedule(election)
    # Expire any stale co-chairmen for this org (affects is_election_manager check)
    from core.enforcement import expire_co_chairmen_for_org
    expire_co_chairmen_for_org(election.organization)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to manage this election.')

    positions = election.positions.all()
    candidates = Candidate.objects.filter(election=election).select_related('user', 'position')
    pool_count = ElectionVoter.objects.filter(election=election).count() if election.status != 'draft' else None

    # Preview pool count for draft
    if election.status == 'draft':
        preview_pool = compute_voter_pool(election)
        pool_preview_count = preview_pool.count()
    else:
        pool_preview_count = pool_count

    position_form = ElectionPositionForm()
    voter_form = VoterPoolForm(instance=election)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_position':
            if election.status not in ['draft', 'open']:
                error_msg = 'Cannot add positions to a closed election.'
                if request.headers.get('HX-Request'):
                    return render(request, 'elections/_positions_partial.html', {
                        'election': election,
                        'positions': election.positions.all(),
                        'candidates': Candidate.objects.filter(election=election).select_related('user', 'position'),
                        'error': error_msg,
                    })
                messages.error(request, error_msg)
            else:
                name = request.POST.get('name', '').strip()
                target_role = request.POST.get('target_role', 'officer')
                valid_roles = ['officer', 'co_chairman', 'chairman']
                error_msg = None
                if not name:
                    error_msg = 'Position name cannot be empty.'
                elif target_role not in valid_roles:
                    error_msg = 'Invalid role selected.'
                elif ElectionPosition.objects.filter(election=election, name__iexact=name).exists():
                    error_msg = f'A position named "{name}" already exists.'
                elif target_role == 'chairman' and ElectionPosition.objects.filter(election=election, target_role='chairman').exists():
                    error_msg = 'An election can only have one Chairman position.'
                else:
                    ElectionPosition.objects.create(election=election, name=name, target_role=target_role)
                if request.headers.get('HX-Request'):
                    from django.template.loader import render_to_string
                    positions_html = render_to_string('elections/_positions_partial.html', {
                        'election': election,
                        'positions': election.positions.all(),
                        'error': error_msg,
                    }, request=request)
                    candidates_html = render_to_string('elections/_candidates_partial.html', {
                        'election': election,
                        'positions': election.positions.all(),
                        'candidates': Candidate.objects.filter(election=election).select_related('user', 'position'),
                    }, request=request)
                    from django.http import HttpResponse
                    return HttpResponse(
                        positions_html +
                        f'<div id="candidates-section" hx-swap-oob="innerHTML">{candidates_html}</div>'
                    )
                if error_msg:
                    messages.error(request, error_msg)
            return redirect('elections:election_manage', election_id=election_id)

        elif action == 'remove_position':
            if election.status != 'draft':
                error_msg = 'Positions cannot be removed after the election is open.'
                if request.headers.get('HX-Request'):
                    return render(request, 'elections/_positions_partial.html', {
                        'election': election,
                        'positions': election.positions.all(),
                        'candidates': Candidate.objects.filter(election=election).select_related('user', 'position'),
                        'error': error_msg,
                    })
                messages.error(request, error_msg)
            else:
                pos_id = request.POST.get('position_id')
                ElectionPosition.objects.filter(id=pos_id, election=election).delete()
            if request.headers.get('HX-Request'):
                from django.template.loader import render_to_string
                from django.http import HttpResponse
                positions_html = render_to_string('elections/_positions_partial.html', {
                    'election': election,
                    'positions': election.positions.all(),
                }, request=request)
                candidates_html = render_to_string('elections/_candidates_partial.html', {
                    'election': election,
                    'positions': election.positions.all(),
                    'candidates': Candidate.objects.filter(election=election).select_related('user', 'position'),
                }, request=request)
                return HttpResponse(
                    positions_html +
                    f'<div id="candidates-section" hx-swap-oob="innerHTML">{candidates_html}</div>'
                )
            return redirect('elections:election_manage', election_id=election_id)

        elif action == 'save_voter_pool':
            if election.status != 'draft':
                error_msg = 'Voter pool cannot be modified after the election is open.'
                if request.headers.get('HX-Request'):
                    preview_pool = compute_voter_pool(election)
                    return render(request, 'elections/_voter_pool_partial.html', {
                        'election': election,
                        'pool_preview_count': preview_pool.count(),
                        'error': error_msg,
                    })
                messages.error(request, error_msg)
            else:
                voter_form = VoterPoolForm(request.POST, instance=election)
                if voter_form.is_valid():
                    voter_form.save()
                    election.refresh_from_db()
            if request.headers.get('HX-Request'):
                preview_pool = compute_voter_pool(election)
                pool_count = preview_pool.count()
                response = render(request, 'elections/_voter_pool_partial.html', {
                    'election': election,
                    'pool_preview_count': pool_count,
                    'voter_pool_description': get_voter_pool_description(election),
                })
                response['HX-Trigger'] = 'poolSaved'
                return response
            return redirect('elections:election_manage', election_id=election_id)

        elif action == 'nominate':
            error_msg = None
            if election.status in ['closed', 'results_released']:
                error_msg = 'Cannot nominate candidates for a closed election.'
            else:
                student_id = request.POST.get('student_id', '').strip()
                pos_id = request.POST.get('position_id')
                try:
                    from memberships.models import Membership
                    # Try student_id first, then employee_id for faculty users
                    try:
                        user = User.objects.get(student_id=student_id, is_active=True)
                    except User.DoesNotExist:
                        user = User.objects.get(employee_id=student_id, is_active=True)
                    position = ElectionPosition.objects.get(id=pos_id, election=election)

                    # CSO elections: any active student in the system is eligible
                    # Regular org elections: candidate must be an active member of the org
                    if not election.organization.is_cso:
                        is_member = Membership.objects.filter(
                            user=user,
                            organization=election.organization,
                            status='active',
                        ).exists()
                        if not is_member:
                            error_msg = f'{user.get_full_name()} is not an active member of {election.organization.name} and cannot be nominated.'

                    if not error_msg:
                        # Block if already nominated for any other position in this election
                        existing_nomination = Candidate.objects.filter(
                            election=election, user=user
                        ).exclude(position=position).first()
                        if existing_nomination:
                            error_msg = f'{user.get_full_name()} is already nominated for "{existing_nomination.position.name}". Remove them first.'
                        else:
                            Candidate.objects.create(
                                election=election,
                                position=position,
                                user=user,
                                nominated_by=request.user,
                            )
                except User.DoesNotExist:
                    error_msg = 'Student ID not found.'
                except ElectionPosition.DoesNotExist:
                    error_msg = 'Invalid position.'
                except Exception:
                    error_msg = 'This candidate is already nominated for this position.'
            if request.headers.get('HX-Request'):
                positions = election.positions.all()
                candidates = Candidate.objects.filter(election=election).select_related('user', 'position')
                return render(request, 'elections/_candidates_partial.html', {
                    'election': election,
                    'positions': positions,
                    'candidates': candidates,
                    'nominate_error': error_msg,
                    'nominate_error_pos': request.POST.get('position_id'),
                })
            if error_msg:
                messages.error(request, error_msg)
            return redirect('elections:election_manage', election_id=election_id)

        elif action == 'remove_candidate':
            if election.status != 'draft':
                error_msg = 'Cannot remove candidates after the election is open.'
                if request.headers.get('HX-Request'):
                    positions = election.positions.all()
                    candidates = Candidate.objects.filter(election=election).select_related('user', 'position')
                    return render(request, 'elections/_candidates_partial.html', {
                        'election': election, 'positions': positions, 'candidates': candidates,
                        'nominate_error': error_msg,
                    })
                messages.error(request, error_msg)
            else:
                cand_id = request.POST.get('candidate_id')
                Candidate.objects.filter(id=cand_id, election=election).delete()
            if request.headers.get('HX-Request'):
                positions = election.positions.all()
                candidates = Candidate.objects.filter(election=election).select_related('user', 'position')
                return render(request, 'elections/_candidates_partial.html', {
                    'election': election, 'positions': positions, 'candidates': candidates,
                })
            return redirect('elections:election_manage', election_id=election_id)

    # Build voter roster for manager (who voted vs. abstained)
    voter_roster = []
    if election.status in ['open', 'closed', 'results_released']:
        voted_user_ids = set(
            Vote.objects.filter(election=election)
            .values_list('voter_id', flat=True)
            .distinct()
        )
        all_voters_qs = ElectionVoter.objects.filter(
            election=election
        ).select_related('user__course').order_by('user__last_name', 'user__first_name')
        voter_roster = [
            {
                'user': ev.user,
                'voted': ev.user_id in voted_user_ids,
            }
            for ev in all_voters_qs
        ]

    voter_pool_description = get_voter_pool_description(election)

    return render(request, 'elections/manage.html', {
        'election': election,
        'positions': positions,
        'candidates': candidates,
        'position_form': position_form,
        'voter_form': voter_form,
        'pool_preview_count': pool_preview_count,
        'is_voter': ElectionVoter.objects.filter(election=election, user=request.user).exists(),
        'voter_pool_configured': pool_preview_count > 0,
        'voter_roster': voter_roster,
        'voter_pool_description': voter_pool_description,
        'voted_count': sum(1 for v in voter_roster if v['voted']),
        'abstained_count': sum(1 for v in voter_roster if not v['voted']),
    })

# ─── Open Election ────────────────────────────────────────────────────────────

@login_required
def election_open_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to manage this election.')

    if election.status != 'draft':
        messages.error(request, 'Only draft elections can be opened.')
        return redirect('elections:election_manage', election_id=election_id)

    if not election.positions.exists():
        messages.error(request, 'Election must have at least one position before opening.')
        return redirect('elections:election_manage', election_id=election_id)

    if not Candidate.objects.filter(election=election).exists():
        messages.error(request, 'Election must have at least one candidate before opening.')
        return redirect('elections:election_manage', election_id=election_id)

    # Fix #8 — block if any position has only one candidate
    for position in election.positions.all():
        count = Candidate.objects.filter(election=election, position=position).count()
        if count < 2:
            messages.error(request, f'Position "{position.name}" must have at least 2 candidates before opening.')
            return redirect('elections:election_manage', election_id=election_id)

    # CRITICAL FIX: Validate voter pool is configured BEFORE showing the form
    pool = compute_voter_pool(election)
    if not pool.exists():
        messages.error(request, 'Configure the voter pool before opening the election.')
        return redirect('elections:election_manage', election_id=election_id)

    from .forms import ElectionOpenForm

    if request.method == 'POST':
        form = ElectionOpenForm(request.POST)
        if not form.is_valid():
            return render(request, 'elections/open_confirm.html', {
                'election': election,
                'form': form,
            })

        open_now = form.cleaned_data.get('open_now', True)
        start = form.cleaned_data.get('start_datetime')
        end = form.cleaned_data['end_datetime']

        if open_now or not start:
            start = timezone.now()

        election.start_datetime = start
        election.end_datetime = end

        is_scheduled = start > timezone.now()

        if is_scheduled:
            # Scheduled open — validate voter pool is configured before saving
            pool = compute_voter_pool(election)
            if not pool.exists():
                messages.error(request, 'Configure the voter pool before scheduling the election.')
                return render(request, 'elections/open_confirm.html', {
                    'election': election,
                    'form': form,
                    'end_value': request.POST.get('end_datetime', ''),
                    'start_value': request.POST.get('start_datetime', ''),
                    'open_now': request.POST.get('open_now', ''),
                })

            # Keep as draft, snapshot pool at open time via task
            election.save(update_fields=['start_datetime', 'end_datetime'])

            try:
                from .tasks import auto_open_election
                auto_open_election.apply_async(
                    args=[election.id],
                    eta=start,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f'Could not schedule auto-open for election {election.id}: {e}.'
                )
                messages.warning(request, 'Auto-open scheduling unavailable — the election will open automatically when you next visit this page at or after the scheduled time.')

            messages.success(request, f'Election "{election.title}" scheduled to open on {start.strftime("%b %d, %Y at %I:%M %p")}.')
            return redirect('elections:election_manage', election_id=election_id)

        # Open immediately — snapshot voter pool now
        pool = compute_voter_pool(election)
        if not pool.exists():
            messages.error(request, 'Voter pool is empty. Configure the voter pool before opening.')
            return render(request, 'elections/open_confirm.html', {
                'election': election,
                'form': form,
                'end_value': request.POST.get('end_datetime', ''),
                'start_value': request.POST.get('start_datetime', ''),
                'open_now': request.POST.get('open_now', 'on'),
            })

        ElectionVoter.objects.filter(election=election).delete()
        ElectionVoter.objects.bulk_create([
            ElectionVoter(election=election, user=user) for user in pool
        ], ignore_conflicts=True)

        election.status = 'open'
        election.save(update_fields=['status', 'start_datetime', 'end_datetime'])

        try:
            from .tasks import auto_close_election
            auto_close_election.apply_async(
                args=[election.id],
                eta=election.end_datetime,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f'Could not schedule auto-close for election {election.id}: {e}. '
                'The election will need to be closed manually.'
            )
            messages.warning(request, 'Auto-close scheduling unavailable — you will need to close this election manually when it ends.')

        from announcements.utils import send_notification
        from django.urls import reverse
        voter_users = list(pool)
        if voter_users:
            send_notification(
                title=f'Election open — {election.title}',
                message=f'The election "{election.title}" for {election.organization.name} is now open. Cast your vote!',
                recipients=voter_users,
                sender=request.user,
                organization=election.organization,
                link_url=reverse('elections:election_vote', kwargs={'election_id': election.id}),
                notification_type='election:open',
            )

        messages.success(request, f'Election "{election.title}" is now open.')
        return redirect('elections:election_manage', election_id=election_id)

    # GET — show the open confirmation form
    form = ElectionOpenForm()
    # Pre-populate with existing scheduled times if rescheduling
    return render(request, 'elections/open_confirm.html', {
        'election': election,
        'form': form,
        'start_value': election.start_datetime.strftime('%Y-%m-%dT%H:%M') if election.start_datetime else '',
        'end_value': election.end_datetime.strftime('%Y-%m-%dT%H:%M') if election.end_datetime else '',
        'open_now': '' if election.start_datetime else 'on',
        'is_reschedule': bool(election.start_datetime),
    })


# ─── Close Election ───────────────────────────────────────────────────────────

@login_required
def election_close_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to manage this election.')

    if request.method == 'POST':
        if election.status != 'open':
            messages.error(request, 'Only open elections can be closed.')
        else:
            election.status = 'closed'
            election.closed_at = timezone.now()
            election.save(update_fields=['status', 'closed_at'])
            # Notify voters that the election has been closed
            from announcements.utils import send_notification
            from django.urls import reverse
            voter_ids = list(ElectionVoter.objects.filter(election=election).values_list('user_id', flat=True))
            from accounts.models import User
            voters = list(User.objects.filter(id__in=voter_ids))
            if voters:
                send_notification(
                    title=f'Election closed — {election.title}',
                    message=f'The election "{election.title}" for {election.organization.name} has been closed.',
                    recipients=voters,
                    sender=request.user,
                    organization=election.organization,
                    link_url=reverse('elections:election_list'),
                    notification_type='election:closed',
                )
            messages.success(request, f'Election "{election.title}" has been closed.')

    return redirect('elections:election_manage', election_id=election_id)


# ─── Release Results ──────────────────────────────────────────────────────────

@login_required
def election_release_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to manage this election.')

    if election.status != 'closed':
        messages.error(request, 'Results can only be released for closed elections.')
        return redirect('elections:election_manage', election_id=election_id)

    total_votes = Vote.objects.filter(election=election).count()

    # Show review page on GET — always allowed
    if request.method == 'GET':
        tally = get_vote_tally(election)
        positions = election.positions.all()
        total_voters = ElectionVoter.objects.filter(election=election).count()
        return render(request, 'elections/release_review.html', {
            'election': election,
            'tally_by_position': [
                (pos, tally.get(str(pos.id), {}).get('candidates', []),
                 tally.get(str(pos.id), {}).get('is_tied', False),
                 tally.get(str(pos.id), {}).get('no_contest', False))
                for pos in positions
            ],
            'total_voters': total_voters,
            'total_votes': total_votes,
            'can_release': total_votes > 0,
        })

    if request.method == 'POST':
        # Fix #7 — block release if no votes cast
        if total_votes == 0:
            messages.error(request, 'No votes were cast in this election. Results cannot be released.')
            return redirect('elections:election_release', election_id=election_id)
        election.status = 'results_released'
        election.is_archived = True
        election.results_released_by = request.user
        election.results_released_at = timezone.now()
        election.save(update_fields=['status', 'is_archived', 'results_released_by', 'results_released_at'])

        from announcements.utils import send_notification
        from django.urls import reverse
        voter_users = list(ElectionVoter.objects.filter(
            election=election
        ).values_list('user', flat=True))
        from accounts.models import User
        recipients = list(User.objects.filter(id__in=voter_users))
        if recipients:
            send_notification(
                title=f'Election results released — {election.title}',
                message=f'The results for "{election.title}" have been released. Check the results page.',
                recipients=recipients,
                sender=request.user,
                organization=election.organization,
                link_url=reverse('elections:election_results', kwargs={'election_id': election.id}),
                notification_type='election:results',
            )
        messages.success(request, 'Results released successfully.')

    from django.urls import reverse
    return redirect(reverse('elections:election_results', kwargs={'election_id': election_id}) + '?view=manage')


# ─── Vote ─────────────────────────────────────────────────────────────────────

def _build_live_tally(election):
    """Build enriched tally with profile pictures for the live count partial."""
    tally = get_vote_tally(election)
    positions = election.positions.prefetch_related('candidates__user')
    enriched = []
    for pos in positions:
        pos_data = tally.get(str(pos.id), {})
        candidates = pos_data.get('candidates', [])
        is_tied = pos_data.get('is_tied', False)
        pic_map = {cand.id: (cand.user.profile_picture.url if cand.user.profile_picture else None)
                   for cand in pos.candidates.all()}
        enriched_candidates = [{**c, 'profile_picture': pic_map.get(c['candidate_id'])} for c in candidates]
        enriched.append((pos, enriched_candidates, is_tied))
    return enriched


@login_required
def election_vote_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    # Enforce time-based open/close regardless of Celery
    election = enforce_election_schedule(election)

    is_voter = ElectionVoter.objects.filter(election=election, user=request.user).exists()
    if not is_voter:
        return HttpResponseForbidden('You are not eligible to vote in this election.')

    if election.status != 'open':
        messages.error(request, 'This election is not currently accepting votes.')
        return redirect('elections:election_list')

    # Enforce start time — election may be 'open' but not yet started
    if election.start_datetime and timezone.now() < election.start_datetime:
        messages.error(request, 'This election has not started yet.')
        return redirect('elections:election_list')

    positions = election.positions.prefetch_related('candidates__user')

    # Track which positions the user has already voted on
    voted_position_ids = set(
        Vote.objects.filter(
            election=election, voter=request.user
        ).values_list('position_id', flat=True)
    )

    if request.method == 'POST':
        errors = []
        # Guard: block if this voter was an adviser during the current academic period,
        # even if their role was changed after the voter snapshot was taken.
        from memberships.models import Membership
        from core.models import AcademicPeriod
        from django.db.models import Q
        current_period = AcademicPeriod.objects.filter(is_current=True).first()
        if current_period:
            is_period_adviser = Membership.objects.filter(
                user=request.user,
                status='active',
            ).filter(
                Q(role='adviser') |
                Q(adviser_since__gte=current_period.start_date, adviser_since__isnull=False)
            ).exists()
        else:
            is_period_adviser = Membership.objects.filter(
                user=request.user, role='adviser', status='active'
            ).exists()
        if is_period_adviser:
            messages.error(request, 'Advisers are not eligible to vote in elections.')
            return redirect('elections:election_list')

        # Also block faculty users regardless of their current org role
        if request.user.is_faculty:
            messages.error(request, 'Faculty advisers are not eligible to vote in elections.')
            return redirect('elections:election_list')

        # Check all unvoted positions have a selection
        for position in positions:
            if position.id in voted_position_ids:
                continue
            candidate_id = request.POST.get(f'position_{position.id}')
            if not candidate_id:
                errors.append(f'You must vote for "{position.name}" — no skipping allowed.')

        if not errors:
            for position in positions:
                if position.id in voted_position_ids:
                    continue
                candidate_id = request.POST.get(f'position_{position.id}')
                try:
                    candidate = Candidate.objects.get(
                        id=candidate_id, position=position, election=election
                    )
                    Vote.objects.create(
                        election=election,
                        position=position,
                        candidate=candidate,
                        voter=request.user,
                    )
                except Candidate.DoesNotExist:
                    errors.append(f'Invalid candidate for {position.name}.')
                except Exception:
                    errors.append(f'You have already voted for {position.name}.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            messages.success(request, 'Your votes have been recorded.')
        return redirect('elections:election_vote', election_id=election_id)

    return render(request, 'elections/vote.html', {
        'election': election,
        'positions': positions,
        'voted_position_ids': voted_position_ids,
        'tally_by_position': _build_live_tally(election),
    })


# ─── Live Count (HTMX partial) ────────────────────────────────────────────────

@login_required
def election_live_count_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    is_voter = ElectionVoter.objects.filter(election=election, user=request.user).exists()
    if not is_voter and not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You are not eligible to view this election.')

    if election.status != 'open':
        return HttpResponseForbidden('Live count is only available while the election is open.')

    tally = get_vote_tally(election)
    positions = election.positions.prefetch_related('candidates__user')

    # Enrich tally candidates with profile picture URLs
    enriched = []
    for pos in positions:
        pos_data = tally.get(str(pos.id), {})
        candidates = pos_data.get('candidates', [])
        is_tied = pos_data.get('is_tied', False)
        pic_map = {cand.id: (cand.user.profile_picture.url if cand.user.profile_picture else None)
                   for cand in pos.candidates.all()}
        enriched_candidates = [{**c, 'profile_picture': pic_map.get(c['candidate_id'])} for c in candidates]
        enriched.append((pos, enriched_candidates, is_tied))

    return render(request, 'elections/_live_count_partial.html', {
        'election': election,
        'tally_by_position': enriched,
    })


# ─── Live Voter Stats (HTMX partial — manager only) ──────────────────────────

@login_required
def election_voter_stats_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to view this.')

    if election.status != 'open':
        return HttpResponseForbidden('Live stats only available while election is open.')

    total_voters = ElectionVoter.objects.filter(election=election).count()
    voted = Vote.objects.filter(election=election).values('voter_id').distinct().count()
    abstained = total_voters - voted

    from django.http import JsonResponse
    return JsonResponse({
        'total_voters': total_voters,
        'voted': voted,
        'abstained': abstained,
    })


# ─── Results ──────────────────────────────────────────────────────────────────

@login_required
def election_results_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    is_voter = ElectionVoter.objects.filter(election=election, user=request.user).exists()
    is_manager = is_election_manager(request.user, election.organization)

    if not is_voter and not is_manager:
        return HttpResponseForbidden('You do not have access to this election.')

    if election.status not in ['results_released', 'closed']:
        messages.info(request, 'Results have not been released yet.')
        return redirect('elections:election_list')

    tally = get_vote_tally(election) if election.status == 'results_released' else {}
    positions = election.positions.all()

    # Track which candidates have already been applied
    from memberships.models import Membership
    promoted_candidate_ids = set()
    deferred_candidate_ids = set()
    in_window_candidate_ids = set()
    self_revokable_candidate_ids = set()
    tied_position_ids = set()
    no_contest_position_ids = set()

    if tally:
        for position in positions:
            pos_data = tally.get(str(position.id), {})
            pos_candidates = pos_data.get('candidates', [])
            is_tied = pos_data.get('is_tied', False)
            no_contest = pos_data.get('no_contest', False)

            if no_contest:
                no_contest_position_ids.add(position.id)
                continue

            if is_tied:
                tied_position_ids.add(position.id)
                continue

            if pos_candidates:
                winner = pos_candidates[0]
                winner_qs = Candidate.objects.filter(id=winner['candidate_id']).values_list('user_id', flat=True)

                # Already applied
                winner_membership = Membership.objects.filter(
                    user_id__in=winner_qs,
                    organization=election.organization,
                    status='active',
                    role=position.target_role,
                ).first()
                if winner_membership:
                    promoted_candidate_ids.add(winner['candidate_id'])
                    continue

                role_order = {'chairman': 4, 'co_chairman': 3, 'officer': 2, 'member': 1}
                target_rank = role_order.get(position.target_role, 0)

                in_temp_window = Membership.objects.filter(
                    user_id__in=winner_qs,
                    organization=election.organization,
                    status='active',
                    role='co_chairman',
                    co_chairman_expiry__isnull=False,
                ).exists()

                from accounts.models import User as UserModel
                winner_user = UserModel.objects.filter(id__in=winner_qs).first()
                in_cso_temp_window = bool(
                    election.organization.is_cso and winner_user and winner_user.cso_admin_expiry
                )

                if in_temp_window or in_cso_temp_window:
                    if target_rank == 4:
                        in_window_candidate_ids.add(winner['candidate_id'])
                    else:
                        winner_user_id = list(winner_qs)
                        is_self = request.user.id in winner_user_id
                        if is_self:
                            self_revokable_candidate_ids.add(winner['candidate_id'])
                        else:
                            in_window_candidate_ids.add(winner['candidate_id'])
                    continue

                is_current_chairman = Membership.objects.filter(
                    user_id__in=winner_qs,
                    organization=election.organization,
                    status='active',
                    role='chairman',
                ).exists()
                if is_current_chairman and target_rank < 4:
                    deferred_candidate_ids.add(winner['candidate_id'])

    # ── Voter participation stats ──────────────────────────────────────────────
    all_voters = ElectionVoter.objects.filter(election=election).select_related('user')
    total_voters = all_voters.count()

    # A voter "voted" if they cast at least one vote
    voted_user_ids = set(
        Vote.objects.filter(election=election)
        .values_list('voter_id', flat=True)
        .distinct()
    )
    total_voted = len(voted_user_ids)
    total_abstained = total_voters - total_voted

    # Build voter list with voted flag (managers only)
    voter_list = [
        {'user': ev.user, 'voted': ev.user_id in voted_user_ids}
        for ev in all_voters.order_by('user__last_name', 'user__first_name')
    ] if is_manager else []

    voter_pool_description = get_voter_pool_description(election) if is_manager else []

    return render(request, 'elections/results.html', {
        'election': election,
        'tally': tally,
        'positions': positions,
        'tally_by_position': [
            (pos, tally.get(str(pos.id), {}).get('candidates', []), tally.get(str(pos.id), {}).get('is_tied', False), tally.get(str(pos.id), {}).get('no_contest', False))
            for pos in positions
        ] if tally else [],
        'is_manager': is_manager,
        'is_voter_only': is_voter and not is_manager,
        'show_promotions': is_manager and request.GET.get('view') == 'manage',
        'promoted_candidate_ids': promoted_candidate_ids,
        'deferred_candidate_ids': deferred_candidate_ids,
        'in_window_candidate_ids': in_window_candidate_ids,
        'self_revokable_candidate_ids': self_revokable_candidate_ids,
        'tied_position_ids': tied_position_ids,
        'no_contest_position_ids': no_contest_position_ids,
        # Voter participation
        'total_voters': total_voters,
        'total_voted': total_voted,
        'total_abstained': total_abstained,
        'voter_list': voter_list,
        'voter_pool_description': voter_pool_description,
    })


# ─── Promote Winners ──────────────────────────────────────────────────────────

def _apply_non_chairman_promotion(candidate, org, requester=None):
    """Apply a non-chairman role change. Returns True if applied, False if blocked."""
    from memberships.models import Membership
    from organizations.models import Role as OrgRole

    target_role = candidate.position.target_role or 'officer'
    custom_role, _ = OrgRole.objects.get_or_create(
        organization=org,
        name=candidate.position.name,
        defaults={'is_active': True}
    )

    # Block direct change if still the active chairman
    if Membership.objects.filter(user=candidate.user, organization=org, status='active', role='chairman').exists():
        return False

    # In 24hr temp co-chairman window
    existing = Membership.objects.filter(
        user=candidate.user, organization=org, status='active',
        role='co_chairman', co_chairman_expiry__isnull=False,
    ).first()

    if existing:
        # Only the person themselves can end their own 24hr window early
        if requester and requester.id != candidate.user.id:
            return False
        # Self-revoke: apply the elected role immediately
        existing.role = target_role
        existing.has_chairman_privileges = target_role == 'co_chairman'
        existing.custom_role = custom_role
        existing.co_chairman_expiry = None
        existing.pending_role = None
        existing.pending_custom_role = None
        existing.save()
    else:
        Membership.objects.update_or_create(
            user=candidate.user,
            organization=org,
            defaults={
                'role': target_role,
                'status': 'active',
                'has_chairman_privileges': target_role == 'co_chairman',
                'custom_role': custom_role,
                'co_chairman_expiry': None,
                'pending_role': None,
                'pending_custom_role': None,
            }
        )
    return True


def _apply_chairman_promotion(candidate, org, note_text, sender):
    """Apply chairman promotion with 24hr handover. For CSO org, also updates is_cso_president.
    Returns False if the winner is currently in a 24hr transition window (cannot become chairman again yet).
    """
    from memberships.models import Membership
    from organizations.models import Role as OrgRole
    from datetime import timedelta
    from core.models import HandoverNote

    # Block if winner is currently in their own 24hr temp window
    if Membership.objects.filter(
        user=candidate.user, organization=org, status='active',
        role='co_chairman', co_chairman_expiry__isnull=False,
    ).exists():
        return False

    # For CSO org — also block if winner still has temp admin expiry set
    if org.is_cso and candidate.user.cso_admin_expiry:
        return False

    custom_role, _ = OrgRole.objects.get_or_create(
        organization=org,
        name=candidate.position.name,
        defaults={'is_active': True}
    )

    outgoing = Membership.objects.filter(organization=org, role='chairman', status='active').first()

    # Promote winner to chairman in org
    Membership.objects.update_or_create(
        user=candidate.user,
        organization=org,
        defaults={
            'role': 'chairman',
            'status': 'active',
            'has_chairman_privileges': True,
            'co_chairman_expiry': None,
            'custom_role': custom_role,
            'pending_role': None,
            'pending_custom_role': None,
        }
    )

    # For CSO org — also update is_cso_president flags
    if org.is_cso:
        candidate.user.is_cso_president = True
        candidate.user.is_cso_admin = True
        candidate.user.cso_admin_expiry = None
        candidate.user.save(update_fields=['is_cso_president', 'is_cso_admin', 'cso_admin_expiry'])

    if outgoing and outgoing.user != candidate.user:
        outgoing_won = Candidate.objects.filter(
            election=candidate.election,
            user=outgoing.user,
        ).exclude(position__target_role='chairman').first()

        # CRITICAL FIX: Use update_or_create to ensure membership is preserved
        outgoing, _ = Membership.objects.update_or_create(
            user=outgoing.user,
            organization=org,
            defaults={
                'role': 'co_chairman',
                'status': 'active',
                'has_chairman_privileges': True,
                'co_chairman_expiry': timezone.now() + timedelta(hours=24),
                'pending_role': outgoing_won.position.target_role if outgoing_won else None,
                'pending_custom_role': (
                    OrgRole.objects.get_or_create(
                        organization=org,
                        name=outgoing_won.position.name,
                        defaults={'is_active': True}
                    )[0] if outgoing_won else None
                ),
            }
        )

        # For CSO org — outgoing president gets 24hr temp admin
        if org.is_cso:
            outgoing.user.is_cso_president = False
            outgoing.user.is_cso_admin = True
            outgoing.user.cso_admin_expiry = timezone.now() + timedelta(hours=24)
            outgoing.user.save(update_fields=['is_cso_president', 'is_cso_admin', 'cso_admin_expiry'])

    # Save handover note
    if note_text and outgoing and outgoing.user != candidate.user:
        HandoverNote.objects.create(
            from_user=outgoing.user if outgoing else sender,
            to_user=candidate.user,
            organization=org,
            type='chairman',
            note=note_text,
        )

    # Notifications
    from announcements.utils import send_notification
    from django.urls import reverse
    if outgoing and outgoing.user != candidate.user:
        msg = (
            f'{candidate.user.get_full_name()} has been elected as the new chairman of {org.name}. '
            f'You have temporary co-chairman access for 24 hours.'
        )
        if outgoing_won:
            msg += f' Your elected role of {outgoing_won.position.name} will be applied once your access ends.'
        if note_text:
            msg += f'\n\nHandover note: {note_text}'
        send_notification(
            title=f'Chairman role transferred — {org.name}',
            message=msg,
            recipients=[outgoing.user],
            sender=sender,
            organization=org,
            is_priority=True,
            link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
            notification_type='election:results',
        )

    send_notification(
        title=f'You are now chairman of {org.name}',
        message=f'Congratulations! You have been elected as chairman of {org.name}.',
        recipients=[candidate.user],
        sender=sender,
        organization=org,
        is_priority=True,
        link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
        notification_type='election:results',
    )


@login_required
def election_promote_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to manage this election.')

    if election.status != 'results_released':
        messages.error(request, 'Promotions can only be applied after results are released.')
        from django.urls import reverse
        return redirect(reverse('elections:election_results', kwargs={'election_id': election_id}) + '?view=manage')

    if request.method == 'POST':
        candidate_ids = request.POST.getlist('promote_candidates')

        if not candidate_ids:
            messages.error(request, 'No candidates selected.')
            from django.urls import reverse
            return redirect(reverse('elections:election_results', kwargs={'election_id': election_id}) + '?view=manage')

        # Split into chairman vs non-chairman
        chairman_candidates = []
        other_candidates = []
        for cand_id in candidate_ids:
            try:
                c = Candidate.objects.select_related('position').get(id=cand_id, election=election)
                # Skip if this position is tied or no contest
                pos_data = get_vote_tally(election).get(str(c.position.id), {})
                if pos_data.get('is_tied', False):
                    messages.warning(request, f'"{c.position.name}" has a tie — cannot apply until resolved.')
                    continue
                if pos_data.get('no_contest', False):
                    messages.warning(request, f'"{c.position.name}" had no votes cast — cannot apply result.')
                    continue
                if c.position.target_role == 'chairman':
                    chairman_candidates.append(cand_id)
                else:
                    other_candidates.append(cand_id)
            except Candidate.DoesNotExist:
                pass

        if chairman_candidates:
            # Store in session and redirect to handover confirmation
            request.session[f'election_promote_{election_id}'] = {
                'chairman_candidates': chairman_candidates,
                'other_candidates': other_candidates,
            }
            return redirect('elections:election_handover_confirm', election_id=election_id)

        # No chairman — process non-chairman promotions directly
        promoted = 0
        for cand_id in other_candidates:
            try:
                candidate = Candidate.objects.select_related('user', 'position').get(id=cand_id, election=election)
                if _apply_non_chairman_promotion(candidate, election.organization, requester=request.user):
                    promoted += 1
                else:
                    messages.warning(request, f'{candidate.user.get_full_name()} — cannot apply this result yet.')
            except Candidate.DoesNotExist:
                pass
        messages.success(request, f'{promoted} result(s) applied.')

    from django.urls import reverse
    return redirect(reverse('elections:election_results', kwargs={'election_id': election_id}) + '?view=manage')


@login_required
def election_handover_confirm_view(request, election_id):
    """Intermediate handover confirmation page when a chairman is being promoted via election."""
    from memberships.models import Membership

    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to manage this election.')

    session_key = f'election_promote_{election_id}'
    pending = request.session.get(session_key)

    if not pending:
        messages.error(request, 'No pending promotion found.')
        from django.urls import reverse
        return redirect(reverse('elections:election_results', kwargs={'election_id': election_id}) + '?view=manage')

    chairman_cand_ids = pending.get('chairman_candidates', [])
    other_cand_ids = pending.get('other_candidates', [])

    # Get chairman candidate details for display
    chairman_candidates = []
    for cand_id in chairman_cand_ids:
        try:
            c = Candidate.objects.select_related('user', 'position').get(id=cand_id, election=election)
            chairman_candidates.append(c)
        except Candidate.DoesNotExist:
            pass

    # Get current chairman
    outgoing = Membership.objects.filter(
        organization=election.organization, role='chairman', status='active'
    ).select_related('user').first()

    if request.method == 'POST':
        note_text = request.POST.get('note', '').strip()

        # Apply chairman promotions with handover
        for candidate in chairman_candidates:
            _apply_chairman_promotion(candidate, election.organization, note_text, request.user)

        # Apply non-chairman promotions
        promoted_others = 0
        for cand_id in other_cand_ids:
            try:
                candidate = Candidate.objects.select_related('user', 'position').get(id=cand_id, election=election)
                if _apply_non_chairman_promotion(candidate, election.organization, requester=request.user):
                    promoted_others += 1
            except Candidate.DoesNotExist:
                pass

        # Clear session
        if session_key in request.session:
            del request.session[session_key]

        total = len(chairman_candidates) + promoted_others
        messages.success(request, f'Handover complete. {total} election result(s) applied.')
        from django.urls import reverse
        return redirect(reverse('elections:election_results', kwargs={'election_id': election_id}) + '?view=manage')

    return render(request, 'elections/handover_confirm.html', {
        'election': election,
        'chairman_candidates': chairman_candidates,
        'outgoing': outgoing,
        'other_count': len(other_cand_ids),
    })


# ─── Cancel Draft Election ────────────────────────────────────────────────────

@login_required
def election_cancel_view(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to manage this election.')

    if election.status != 'draft':
        messages.error(request, 'Only draft elections can be cancelled.')
        return redirect('elections:election_manage', election_id=election_id)

    if request.method == 'POST':
        election.delete()
        messages.success(request, 'Election cancelled and deleted.')
        return redirect('elections:election_list')

    return redirect('elections:election_manage', election_id=election_id)


@login_required
def election_delete_view(request, election_id):
    """
    Hard-delete a closed election (no results released yet).
    Draft elections use the cancel view instead.
    Results-released elections are permanent history and cannot be deleted.
    """
    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return HttpResponseForbidden('You do not have permission to delete this election.')

    if election.status != 'closed':
        messages.error(request, 'Only closed elections (with no results released) can be deleted.')
        return redirect('elections:election_manage', election_id=election_id)

    if request.method == 'POST':
        title = election.title
        election.delete()
        messages.success(request, f'Election "{title}" has been permanently deleted.')
        return redirect('elections:election_list')

    return redirect('elections:election_manage', election_id=election_id)


# ─── Admin Archive ────────────────────────────────────────────────────────────

@login_required
def admin_archive_view(request):
    if not request.user.is_cso_admin and not request.user.is_cso_president:
        return HttpResponseForbidden('Access restricted to CSO administrators.')

    elections = Election.objects.filter(
        is_archived=True
    ).select_related('organization', 'created_by').order_by('-results_released_at')

    return render(request, 'elections/admin_archive.html', {'elections': elections})


@login_required
def admin_archive_detail_view(request, election_id):
    if not request.user.is_cso_admin and not request.user.is_cso_president:
        return HttpResponseForbidden('Access restricted to CSO administrators.')

    election = get_object_or_404(Election, id=election_id, is_archived=True)
    tally = get_vote_tally(election)
    positions = election.positions.all()
    total_voters = ElectionVoter.objects.filter(election=election).count()
    total_votes = Vote.objects.filter(election=election).count()

    return render(request, 'elections/admin_archive_detail.html', {
        'election': election,
        'tally': tally,
        'positions': positions,
        'tally_by_position': [(pos, tally.get(str(pos.id), [])) for pos in positions],
        'total_voters': total_voters,
        'total_votes': total_votes,
    })


# ─── Member search (for nomination autocomplete) ──────────────────────────────

@login_required
def election_member_search_view(request, election_id):
    """Return JSON list of candidates matching a name or student ID query.
    For CSO elections: searches all active students in the system.
    For regular org elections: searches only active members of the org.
    """
    from django.http import JsonResponse
    from memberships.models import Membership

    election = get_object_or_404(Election, id=election_id)

    if not is_election_manager(request.user, election.organization):
        return JsonResponse({'results': []}, status=403)

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    from django.db.models import Q

    if election.organization.is_cso:
        # CSO: any active student in the system is eligible
        from accounts.models import User
        users = User.objects.filter(
            is_active=True,
        ).filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(student_id__icontains=q)
        )[:10]
        results = [
            {
                'student_id': u.student_id,
                'name': u.get_full_name(),
            }
            for u in users
        ]
    else:
        # Regular org: only active members of the org
        members = Membership.objects.filter(
            organization=election.organization,
            status='active',
        ).filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__student_id__icontains=q)
        ).select_related('user')[:10]
        results = [
            {
                'student_id': m.user.student_id,
                'name': m.user.get_full_name(),
            }
            for m in members
        ]

    return JsonResponse({'results': results})
