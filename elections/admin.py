from django.contrib import admin
from .models import Election, ElectionPosition, ElectionVoter, Candidate, Vote

admin.site.register(Election)
admin.site.register(ElectionPosition)
admin.site.register(ElectionVoter)
admin.site.register(Candidate)
admin.site.register(Vote)
