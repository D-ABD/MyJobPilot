"""Administration du référentiel documentaire."""
from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("nom", "eleve", "type", "taille", "content_type", "date_upload")
    list_filter = ("type", "date_upload")
    search_fields = ("nom", "eleve__username", "eleve__email")
    list_select_related = ("eleve",)
    readonly_fields = ("date_upload",)

    def get_queryset(self, request):
        return super().get_queryset(request).defer("contenu")
