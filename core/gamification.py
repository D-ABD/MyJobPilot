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
        # Import local : comptes.notifications dépend des modèles de comptes.
        from comptes.models import TypeNotification
        from comptes.notifications import creer_notification

        for attribution in nouveaux:
            badge = attribution.badge
            creer_notification(
                destinataire=utilisateur,
                type=TypeNotification.BADGE_OBTENU,
                message=f"🏆 Badge débloqué : {badge.nom}",
                lien=f"/mon-compte/badges/#badge-{badge.slug}",
            )
    return nouveaux


def progression_badges(utilisateur):
    """Retourne les compteurs servant à présenter les badges à venir."""
    return compter_progression(utilisateur)


_COMPTEUR_PAR_TYPE_BADGE = {
    Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT: "prospections_contactees",
    Badge.TypeCondition.CANDIDATURES_COUNT: "candidatures",
    Badge.TypeCondition.RELANCES_COUNT: "relances",
}


def calculer_prochain_badge(utilisateur, type_condition, compteurs=None):
    """Retourne le prochain badge actif à atteindre dans une catégorie."""
    if compteurs is None:
        compteurs = compter_progression(utilisateur)
    compteur_actuel = compteurs.get(_COMPTEUR_PAR_TYPE_BADGE.get(type_condition), 0)
    badges = list(
        Badge.objects.filter(est_actif=True, type_condition=type_condition)
        .order_by("seuil", "ordre_affichage", "pk")
    )
    if not badges:
        return {
            "prochain_badge": None,
            "compteur_actuel": compteur_actuel,
            "seuil_cible": None,
            "manque": 0,
            "progression": 1.0,
            "progression_pourcentage": 100,
            "tous_obtenus": True,
        }

    obtenus_ids = set(
        BadgeObtenu.objects.filter(utilisateur=utilisateur, badge__in=badges)
        .values_list("badge_id", flat=True)
    )
    prochain = next(
        (
            badge for badge in badges
            if badge.pk not in obtenus_ids and badge.seuil > compteur_actuel
        ),
        None,
    )
    if prochain is None:
        tous_obtenus = len(obtenus_ids) == len(badges)
        return {
            "prochain_badge": None,
            "compteur_actuel": compteur_actuel,
            "seuil_cible": None,
            "manque": 0,
            "progression": 1.0 if tous_obtenus else 0.0,
            "progression_pourcentage": 100 if tous_obtenus else 0,
            "tous_obtenus": tous_obtenus,
        }

    progression = min(compteur_actuel / prochain.seuil, 1.0)
    return {
        "prochain_badge": prochain,
        "compteur_actuel": compteur_actuel,
        "seuil_cible": prochain.seuil,
        "manque": max(prochain.seuil - compteur_actuel, 0),
        "progression": progression,
        "progression_pourcentage": round(progression * 100),
        "tous_obtenus": False,
    }


def calculer_progression_categories(utilisateur):
    """Calcule les trois progressions à partir d'un seul jeu de compteurs."""
    compteurs = compter_progression(utilisateur)
    return {
        "prospections": calculer_prochain_badge(
            utilisateur, Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT, compteurs=compteurs
        ),
        "candidatures": calculer_prochain_badge(
            utilisateur, Badge.TypeCondition.CANDIDATURES_COUNT, compteurs=compteurs
        ),
        "relances": calculer_prochain_badge(
            utilisateur, Badge.TypeCondition.RELANCES_COUNT, compteurs=compteurs
        ),
    }


def calculer_derniers_badges(utilisateur, limite=5):
    """Retourne les attributions récentes en chargeant les badges en une requête."""
    return list(
        BadgeObtenu.objects.filter(utilisateur=utilisateur)
        .select_related("badge")
        .order_by("-date_obtention")[:limite]
    )


def verifier_et_notifier_progression(utilisateur):
    """Notifie une seule fois quand l'élève approche d'un badge actif."""
    from comptes.models import Notification, TypeNotification
    from comptes.notifications import creer_notification

    progression_categories = calculer_progression_categories(utilisateur)
    liens_deja_notifies = set(
        Notification.objects.filter(
            destinataire=utilisateur,
            type=TypeNotification.PROGRESSION_BADGE,
        ).values_list("lien", flat=True)
    )
    notifications_creees = []

    for categorie in ("prospections", "candidatures", "relances"):
        progression = progression_categories[categorie]
        manque = progression["manque"]
        badge = progression["prochain_badge"]
        if progression["tous_obtenus"] or badge is None or not 0 < manque <= 5:
            continue

        lien = f"/mon-compte/badges/#badge-{badge.slug}"
        if lien in liens_deja_notifies:
            continue
        notification = creer_notification(
            destinataire=utilisateur,
            type=TypeNotification.PROGRESSION_BADGE,
            message=f"Plus que {manque} pour débloquer {badge.nom} !",
            lien=lien,
        )
        if notification is not None:
            notifications_creees.append(notification)
            liens_deja_notifies.add(lien)

    return notifications_creees


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
