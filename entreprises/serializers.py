"""Sérialise les prospections pour l'API JSON."""
from rest_framework import serializers

from .models import Entreprise, Prospection


class EntrepriseSerializer(serializers.ModelSerializer):
    nb_prospections = serializers.IntegerField(read_only=True)

    class Meta:
        model = Entreprise
        fields = (
            "id", "nom", "secteur", "ville", "code_postal", "site_web",
            "contact_nom", "contact_email", "contact_telephone", "date_creation",
            "nb_prospections",
        )
        read_only_fields = fields


class EntrepriseProspectionSerializer(serializers.ModelSerializer):
    """Format compact conservé pour l'entreprise imbriquée dans l'API prospections."""

    class Meta:
        model = Entreprise
        fields = ("id", "nom", "ville")


class ProspectionSerializer(serializers.ModelSerializer):
    entreprise = EntrepriseProspectionSerializer(read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    type_contrat_display = serializers.CharField(
        source="get_type_contrat_display",
        read_only=True,
    )

    class Meta:
        model = Prospection
        fields = (
            "id",
            "entreprise",
            "statut",
            "statut_display",
            "type_contrat",
            "type_contrat_display",
            "date_creation",
            "date_modification",
        )
        read_only_fields = fields
