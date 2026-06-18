from django import forms
from django.utils import timezone
from .models import Election, ElectionPosition, Candidate


class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ['title', 'description', 'academic_period']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ElectionOpenForm(forms.Form):
    """Shown when the manager clicks Open Election — sets timing."""
    open_now = forms.BooleanField(required=False, initial=True, label='Open immediately')
    start_datetime = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Scheduled start (optional)',
    )
    end_datetime = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Closing date & time',
    )

    def clean(self):
        cleaned_data = super().clean()
        open_now = cleaned_data.get('open_now')
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')
        now = timezone.now()

        if not end:
            self.add_error('end_datetime', 'Closing time is required.')
            return cleaned_data

        if end <= now:
            self.add_error('end_datetime', 'Closing time must be in the future.')

        if not open_now and start:
            if start <= now:
                self.add_error('start_datetime', 'Scheduled start must be in the future.')
            if end and start and end <= start:
                self.add_error('end_datetime', 'Closing time must be after the start time.')

        return cleaned_data


class ElectionPositionForm(forms.ModelForm):
    class Meta:
        model = ElectionPosition
        fields = ['name', 'order']
        widgets = {
            'order': forms.NumberInput(attrs={'min': 0}),
        }


class VoterPoolForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = [
            'voters_all_students',
            'voters_org_members',
            'voters_org_officers',
            'voters_all_officers',
            'voters_all_chairmen',
            'voters_cso_officers',
            'voters_specific_orgs',
            'voters_specific_users',
        ]
        widgets = {
            'voters_specific_orgs': forms.CheckboxSelectMultiple(),
            'voters_specific_users': forms.CheckboxSelectMultiple(),
        }
