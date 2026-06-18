from django.contrib import admin
from .models import Board, Post, PostReaction

admin.site.register(Board)
admin.site.register(Post)
admin.site.register(PostReaction)
