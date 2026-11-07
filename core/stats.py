"""Calculs des indicateurs des cockpits MyJobPilot."""
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from comptes.models import Centre, Utilisateur
from comptes.scope_utils import centres_du_superviseur
from entreprises.models import Entreprise, Prospection, Statut
from rgpd.models import DemandeRGPD, StatutDemande


def _semaines(queryset, champ_date="date_creation"):
    """Retourne toujours les huit semaines complètes, de S-7 à cette semaine."""
    aujourd_hui = timezone.localdate()
    lundi_cette_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    labels = [f"S-{semaine}" for semaine in range(7, 0, -1)] + ["Cette semaine"]
    valeurs = []
    for decalage in range(7, -1, -1):
        debut = lundi_cette_semaine - timedelta(weeks=decalage)
        fin = debut + timedelta(days=7)
        valeurs.append(queryset.filter(
            **{f"{champ_date}__date__gte": debut, f"{champ_date}__date__lt": fin}
        ).count())
    return {"labels": labels, "data": valeurs}


def _repartition_statuts(queryset):
    compteurs = dict(queryset.values_list("statut").annotate(total=Count("pk")))
    return {
        "labels": [libelle for _, libelle in Statut.choices],
        "data": [compteurs.get(code, 0) for code, _ in Statut.choices],
    }


def _mois_12(queryset, champ_date):
    """Comptes mensuels sur les douze derniers mois calendaires, zéros inclus."""
    aujourd_hui = timezone.localdate()
    mois_courant = date(aujourd_hui.year, aujourd_hui.month, 1)
    mois = []
    for recul in range(11, -1, -1):
        index = mois_courant.year * 12 + mois_courant.month - 1 - recul
        annee, mois_numero_zero = divmod(index, 12)
        debut = date(annee, mois_numero_zero + 1, 1)
        if debut.month == 12:
            fin = date(debut.year + 1, 1, 1)
        else:
            fin = date(debut.year, debut.month + 1, 1)
        mois.append((debut, fin))
    labels = [debut.strftime("%b %Y") for debut, _ in mois]
    data = [queryset.filter(
        **{f"{champ_date}__date__gte": debut, f"{champ_date}__date__lt": fin}
    ).count() for debut, fin in mois]
    return {"labels": labels, "data": data}


def _chart(key, chart_type, title, labels, values):
    return {"key": key, "type": chart_type, "title": title, "labels": labels, "data": values}


def calculer_stats_eleve(eleve):
    prospections = Prospection.objects.filter(eleve=eleve).select_related("entreprise")
    total = prospections.count()
    candidatures = prospections.filter(statut=Statut.CANDIDATURE_ENVOYEE).count()
    entretiens = prospections.filter(statut=Statut.ENTRETIEN_PROGRAMME).count()
    depassees = prospections.exclude(statut=Statut.A_CONTACTER).count()
    taux_reponse = round(depassees * 100 / total) if total else 0
    relances = prospections.filter(date_relance__gte=timezone.localdate()).order_by(
        "date_relance", "pk"
    )[:3]
    repartition = _repartition_statuts(prospections)
    activite = _semaines(prospections)
    return {
        "kpis": [
            {"label": "Total de mes prospections", "value": total},
            {"label": "Candidatures envoyées", "value": candidatures},
            {"label": "Entretiens programmés", "value": entretiens},
            {"label": "Taux de réponse", "value": f"{taux_reponse}%"},
        ],
        "charts": {
            "statuts": _chart("statuts", "doughnut", "Répartition par statut", repartition["labels"], repartition["data"]),
            "activite": _chart("activite", "line", "Évolution des prospections", activite["labels"], activite["data"]),
        },
        "relances": relances,
    }


def calculer_stats_superviseur(superviseur):
    centres_ids = centres_du_superviseur(superviseur)
    eleves = Utilisateur.objects.filter(
        role=Utilisateur.Role.ELEVE, centre_id__in=centres_ids
    ).select_related("centre")
    prospections = Prospection.objects.filter(eleve__in=eleves)
    nb_eleves = eleves.count()
    valides = eleves.filter(is_valide=True).count()
    entretiens = prospections.filter(statut=Statut.ENTRETIEN_PROGRAMME).count()
    centres = list(Centre.objects.filter(pk__in=centres_ids).order_by("nom"))
    centres_chart = [
        (centre.nom, eleves.filter(centre_id=centre.pk).count()) for centre in centres
    ]
    recent_cutoff = timezone.now() - timedelta(days=14)
    actifs_ids = prospections.filter(date_creation__gte=recent_cutoff).values_list(
        "eleve_id", flat=True
    ).distinct()
    sans_activite = eleves.exclude(pk__in=actifs_ids).order_by("username")
    repartition = _repartition_statuts(prospections)
    activite = _semaines(prospections)
    return {
        "kpis": [
            {"label": "Élèves suivis", "value": nb_eleves},
            {"label": "Prospections du scope", "value": prospections.count()},
            {"label": "Taux de validation", "value": f"{round(valides * 100 / nb_eleves) if nb_eleves else 0}%"},
            {"label": "Entretiens décrochés", "value": entretiens},
        ],
        "charts": {
            "centres": _chart("centres", "bar", "Élèves par centre", [nom for nom, _ in centres_chart], [n for _, n in centres_chart]),
            "activite": _chart("activite", "line", "Activité du scope", activite["labels"], activite["data"]),
            "statuts": _chart("statuts", "doughnut", "Répartition des statuts", repartition["labels"], repartition["data"]),
        },
        "eleves_sans_activite": sans_activite,
    }


def calculer_stats_admin():
    eleves = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE)
    superviseurs = Utilisateur.objects.filter(role=Utilisateur.Role.SUPERVISEUR)
    demandes_ouvertes = DemandeRGPD.objects.filter(
        statut__in=[StatutDemande.RECUE, StatutDemande.EN_COURS]
    )
    retard = demandes_ouvertes.filter(
        date_demande__lt=timezone.now() - timedelta(days=25)
    ).count()
    repartition = _repartition_statuts(Prospection.objects.all())
    centres = list(Centre.objects.annotate(
        nombre=Count("utilisateurs", filter=Q(utilisateurs__role=Utilisateur.Role.ELEVE))
    ).order_by("nom"))
    demandes_chart = _mois_12(DemandeRGPD.objects.all(), "date_demande")
    return {
        "kpis": [
            {"label": "Total élèves", "value": eleves.count()},
            {"label": "Total superviseurs", "value": superviseurs.count()},
            {"label": "Total entreprises", "value": Entreprise.objects.count()},
            {"label": "Demandes RGPD en attente", "value": demandes_ouvertes.count(), "variant": "danger" if retard else "primary", "detail": f"{retard} en retard (> 25 jours)"},
        ],
        "charts": {
            "prospections_mois": _chart("prospections_mois", "line", "Prospections par mois", *_mois_12(Prospection.objects.all(), "date_creation").values()),
            "statuts": _chart("statuts", "doughnut", "Répartition globale des statuts", repartition["labels"], repartition["data"]),
            "centres": _chart("centres", "bar", "Élèves par centre", [centre.nom for centre in centres], [centre.nombre for centre in centres]),
            "demandes_mois": _chart("demandes_mois", "line", "Demandes RGPD par mois", demandes_chart["labels"], demandes_chart["data"]),
        },
        "stats": {"demandes_rgpd_retard": retard},
    }
