from django.contrib import admin

from .models import Thing


@admin.register(Thing)
class ThingAdmin(admin.ModelAdmin):
    list_display = ("pk", "name")
