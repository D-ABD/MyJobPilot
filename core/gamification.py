"""Attribution explicite des badges et compteurs de progression."""
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery

from entreprises.models import Prospection, Relance, Statut

from .models import Badge, BadgeObtenu, Niveau


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


def _xp_depuis_compteurs(compteurs):
    return (
        compteurs["prospections_contactees"] * 10
        + compteurs["candidatures"] * 20
        + compteurs["relances"] * 10
    )


def calculer_xp(utilisateur):
    """Calcule les XP à partir des compteurs canoniques de gamification."""
    return _xp_depuis_compteurs(compter_progression(utilisateur))


def calculer_niveau(xp):
    """Retourne le niveau correspondant à XP et la progression vers le suivant."""
    niveaux = list(Niveau.objects.filter(est_actif=True).order_by("-seuil_min"))
    niveau_actuel = next((niveau for niveau in niveaux if niveau.seuil_min <= xp), None)
    if niveau_actuel is None:
        return {
            "nom": "—",
            "seuil_min": None,
            "seuil_max": None,
            "xp_dans_niveau": xp,
            "xp_pour_suivant": None,
            "progression": 0.0,
            "progression_pourcentage": 0,
            "est_max": False,
            "niveau_suivant_nom": None,
        }

    suivant = next(
        (niveau for niveau in reversed(niveaux) if niveau.seuil_min > niveau_actuel.seuil_min),
        None,
    )
    xp_dans_niveau = xp - niveau_actuel.seuil_min
    if suivant is None:
        return {
            "nom": niveau_actuel.nom,
            "seuil_min": niveau_actuel.seuil_min,
            "seuil_max": None,
            "xp_dans_niveau": xp_dans_niveau,
            "xp_pour_suivant": None,
            "progression": 1.0,
            "progression_pourcentage": 100,
            "est_max": True,
            "niveau_suivant_nom": None,
        }

    intervalle = suivant.seuil_min - niveau_actuel.seuil_min
    return {
        "nom": niveau_actuel.nom,
        "seuil_min": niveau_actuel.seuil_min,
        "seuil_max": suivant.seuil_min,
        "xp_dans_niveau": xp_dans_niveau,
        "xp_pour_suivant": suivant.seuil_min - xp,
        "progression": min(1.0, max(0.0, xp_dans_niveau / intervalle)),
        "progression_pourcentage": round(
            100 * min(1.0, max(0.0, xp_dans_niveau / intervalle))
        ),
        "est_max": False,
        "niveau_suivant_nom": suivant.nom,
    }


def calculer_progression_utilisateur(utilisateur):
    """Assemble XP, niveau et résumé de badges avec des compteurs partagés."""
    compteurs = compter_progression(utilisateur)
    xp = _xp_depuis_compteurs(compteurs)
    resume = resume_badges(utilisateur)
    return {
        "xp": xp,
        "niveau": calculer_niveau(xp),
        "points": resume["points_total"],
        "badges_obtenus": resume["badges_obtenus_count"],
        "badges_total": Badge.objects.filter(est_actif=True).count(),
        "compteurs_badges": compteurs,
        "resume_badges": resume,
    }


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
        utilisateur