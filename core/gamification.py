"""Attribution explicite des badges et compteurs de progression."""
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery

from entreprises.models import Prospection, Relance, Statut

from .models import Badge, BadgeObtenu


STATUTS_CANDIDATURE = (
    Statut.CANDIDATURE_ENVOYEE,
    Statut.EN_ATTENTE,
    Statut.ENTRETIEN_PROGRAMME,
    Statut.REFUS,
    Statut.ACCEPTE,
)


def compter_progression(utilisateur):
    """Compte les trois familles sans charger les objets de prospection."""
    prospections = Prospection.objects.filter(eleve_id=utilisateur.pk)
    compteurs = prospections.aggregate(
        prospections_contactees=Count(
            "pk",
            filter=~Q(statut__in=(Statut.A_CONTACTER, Statut.TERMINEE)),
        ),
        candidatures=Count("pk", filter=Q(statut__in=STATUTS_CANDIDATURE)),
    )
    compteurs["relances"] = Relance.objects.filter(
        prospection__eleve_id=utilisateur.pk
    ).count()
    return compteurs


def verifier_et_attribuer_badges(utilisateur):
    """Attribue de façon idempotente tous les badges actifs dont le seuil est atteint.

    Appels explicites (pas de signaux Django), cohérent avec le lot 21a.
    Appelé aussi à l'ouverture du dashboard élève et de la page badges pour
    rattraper les attributions historiques.

    Les deux compteurs Prospection utilisent un seul aggregate(). Le compteur
    Relance est intégré comme sous-requête COUNT à la lecture groupée des badges;
    l'existence d'une attribution est vérifiée dans cette même requête. La
    dernière requête est le bulk_create idempotent.
    """
    prospections = Prospection.objects.filter(eleve_id=utilisateur.pk)
    compteurs = prospections.aggregate(
        prospections_contactees=Count(
            "pk",
            filter=~Q(statut__in=(Statut.A_CONTACTER, Statut.TERMINEE)),
        ),
        candidatures=Count("pk", filter=Q(statut__in=STATUTS_CANDIDATURE)),
    )

    relances_par_eleve = (
        Relance.objects.filter(prospection__eleve_id=utilisateur.pk)
        .order_by()
        .values("prospection__eleve_id")
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )
    attributions_existantes = BadgeObtenu.objects.filter(
        utilisateur_id=utilisateur.pk,
        badge_id=OuterRef("pk"),
    )
    badges = Badge.objects.filter(est_actif=True).annotate(
        deja_obtenu=Exists(attributions_existantes),
        nombre_relances=Subquery(relances_par_eleve, output_field=IntegerField()),
    )

    nouveaux = []
    for badge in badges:
        if badge.deja_obtenu:
            continue
        if badge.type_condition == Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT:
            valeur = compteurs["prospections_contactees"]
        elif badge.type_condition == Badge.TypeCondition.CANDIDATURES_COUNT:
            valeur = compteurs["candidatures"]
        elif badge.type_condition == Badge.TypeCondition.RELANCES_COUNT:
            valeur = badge.nombre_relances or 0
        else:
            continue
        if valeur >= badge.seuil:
            nouveaux.append(BadgeObtenu(utilisateur=utilisateur, badge=badge))

    if nouveaux:
        BadgeObtenu.objects.bulk_create(nouveaux, ignore_conflicts=True)
    return nouveaux


def progression_badges(utilisateur):
    """Retourne les compteurs servant à présenter les badges à venir."""
    return compter_progression(utilisateur)


def resume_badges(utilisateur):
    """Données compactes pour les cartes de dashboard et les fiches staff."""
    obtenus = list(
        BadgeObtenu.objects.filter(utilisateur=utilisateur)
        .select_related("badge")
        .order_by("-date_obtention")
    )
    return {
        "points_total": utilisateur.points_total,
        "badges_obtenus": obtenus,
        "badges_obtenus_count": len(obtenus),
        "badges_total_count": Badge.objects.count(),
    }
