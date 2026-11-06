"""Sérialise les prospections pour l'API JSON."""
from rest_framework import serializers

from .models import Entreprise, Prospection


class EntrepriseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entreprise
        fields = ("id", "nom", "ville")


class ProspectionSerializer(serializers.ModelSerializer):
    entreprise = EntrepriseSerializer(read_only=True)
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
