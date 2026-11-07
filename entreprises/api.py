"""Endpoints JSON de l'application."""
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from comptes.models import Utilisateur
from comptes.scope_utils import centres_du_superviseur
from entreprises.models import Prospection
from entreprises.serializers import EntrepriseSerializer, ProspectionSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def prospections_list(request):
    """Retourne les prospections visibles par l'utilisateur connecté."""
    role = request.user.role
    if role == Utilisateur.Role.ELEVE:
        queryset = Prospection.objects.filter(eleve=request.user)
    elif role == Utilisateur.Role.SUPERVISEUR:
        centres = centres_du_superviseur(request.user)
        queryset = Prospection.objects.filter(
            Q(eleve=request.user)
            | Q(eleve__role=Utilisateur.Role.ELEVE, eleve__centre__in=centres)
        )
    elif role == Utilisateur.Role.ADMIN:
        queryset = Prospection.objects.all()
    else:
        return Response({"detail": "Rôle non autorisé."}, status=403)

    queryset = queryset.select_related("entreprise").order_by("-date_modification")
    return Response(ProspectionSerializer(queryset, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entreprises_list(request):
    """Retourne les entreprises visibles et filtrées pour l'utilisateur courant."""
    from entreprises.views import entreprises_reference_filtrees

    entreprises = entreprises_reference_filtrees(request.user, request.query_params)
    return Response(EntrepriseSerializer(entreprises, many=True).data)
