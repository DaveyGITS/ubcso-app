from django.contrib import admin
from .models import (
    Organization, OrganizationCategory, OrganizationCategoryLink, Role, OrganizationRequest,
    AccreditationApplication, AccreditationDocument, OfficialFormLink, OrganizationRegistration,
    RenewalRequirement,
)

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'status', 'is_cso', 'is_active', 'date_created']
    list_filter = ['category', 'status', 'is_cso', 'is_active']
    search_fields = ['name']

@admin.register(OrganizationCategory)
class OrganizationCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'is_active']

@admin.register(OrganizationRequest)
class OrganizationRequestAdmin(admin.ModelAdmin):
    list_display = ['organization_name', 'requester', 'status', 'created_at']
    list_filter = ['status']

@admin.register(AccreditationApplication)
class AccreditationApplicationAdmin(admin.ModelAdmin):
    list_display = ['organization', 'registration_type', 'status', 'submitted_at', 'reviewed_by']
    list_filter = ['status', 'registration_type']
    search_fields = ['organization__name']

@admin.register(AccreditationDocument)
class AccreditationDocumentAdmin(admin.ModelAdmin):
    list_display = ['document_type', 'application', 'uploaded_at']
    search_fields = ['document_type', 'application__organization__name']

@admin.register(OfficialFormLink)
class OfficialFormLinkAdmin(admin.ModelAdmin):
    list_display = ['label', 'url', 'updated_by', 'updated_at']
    search_fields = ['label']

@admin.register(RenewalRequirement)
class RenewalRequirementAdmin(admin.ModelAdmin):
    list_display = ['status', 'updated_by', 'updated_at']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Status', {
            'fields': ('status',)
        }),
        ('Documents', {
            'fields': ('required_documents', 'optional_documents'),
            'description': 'Enter document types as a JSON list, e.g. ["Letter of Intent", "Form A", "Form B"]'
        }),
        ('Metadata', {
            'fields': ('updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(OrganizationRegistration)
class OrganizationRegistrationAdmin(admin.ModelAdmin):
    list_display = ['org_name', 'category', 'submitted_by', 'proposed_chairman', 'status', 'created_at', 'reviewed_by']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['org_name', 'submitted_by__email', 'proposed_chairman__email']
    readonly_fields = ['created_at', 'reviewed_at']
    
    fieldsets = (
        ('Organization Details', {
            'fields': ('org_name', 'org_registration_number', 'category', 'submitted_by')
        }),
        ('Chairman', {
            'fields': ('proposed_chairman',)
        }),
        ('Proof of Existence', {
            'fields': ('proof_message', 'proof_document')
        }),
        ('Review', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'admin_remarks', 'created_organization')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )