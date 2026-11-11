"""Calculs des indicateurs des cockpits MyJobPilot."""
from datetime import date, timedelta
from math import ceil

from django.db.models import Count, Q
from django.utils import timezone

from comptes.models import Centre, Utilisateur
from comptes.scope_utils import centres_du_superviseur
from entreprises.models import Entreprise, Prospection, Statut
from .models import Objectif
from rgpd.models import DemandeRGPD, StatutDemande


def calculer_atteinte_objectif(objectif):
    """Calcule la progression sur la période de l'objectif.

    Les prospections/semaine sont une moyenne sur les semaines couvertes ;
    candidatures/mois compte uniquement le statut CANDIDATURE_ENVOYEE.
    """
    periode = (objectif.periode_debut, objectif.periode_fin)
    if objectif.type == Objectif.Type.PROSPECTIONS_SEMAINE:
        prospections = Prospection.objects.filter(
            eleve=objectif.eleve,
            date_creation__date__range=periode,
        )
        semaines = max(1, ceil(((objectif.periode_fin - objectif.periode_debut).days + 1) / 7))
        valeur_actuelle = prospections.count() / semaines
    elif objectif.type == Objectif.Type.CANDIDATURES_MOIS:
        valeur_actuelle = Prospection.objects.filter(
            eleve=objectif.eleve,
            statut=Statut.CANDIDATURE_ENVOYEE,
            date_candidature__range=periode,
        ).count()
    else:
        valeur_actuelle = 0

    pourcentage = min(100, valeur_actuelle / objectif.valeur * 100) if objectif.valeur else 0
    statut = "atteint" if pourcentage >= 100 else "en_cours" if pourcentage >= 50 else "en_retard"
    return {
        "valeur_cible": objectif.valeur,
        "valeur_actuelle": valeur_actuelle,
        "pourcentage": round(pourcentage),
        "statut": statut,
    }


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


PERIODES_DASHBOARD = {"7": 7, "30": 30, "90": 90, "all": None}


def normaliser_periode_dashboard(valeur):
    """Retourne une période autorisée, avec 30 jours par défaut."""
    return valeur if valeur in PERIODES_DASHBOARD else "30"


def debut_periode_dashboard(periode):
    """Début inclusif de la période sélectionnée, ou None pour tout l'historique."""
    jours = PERIODES_DASHBOARD[normaliser_periode_dashboard(periode)]
    return timezone.localdate() - timedelta(days=jours - 1) if jours else None


def filtrer_prospections_periode(prospections, periode):
    debut = debut_periode_dashboard(periode)
    if debut:
        return prospections.filter(date_creation__date__gte=debut)
    return prospections


def calculer_kpis_dashboard(eleve_ids, periode="30"):
    """Calcule les KPI des élèves sur 7, 30, 90 jours ou tout l'historique.

    Le taux rapporte les prospections créées dans la période qui sont
    actuellement acceptées ; les relances couvrent les sept prochains jours.
    """
    prospections = filtrer_prospections_periode(
        Prospection.objects.filter(eleve_id__in=eleve_ids), periode
    )
    statuts = dict(prospections.values("statut").annotate(total=Count("pk")).values_list("statut", "total"))
    par_statut = [
        {"code": code, "label": libelle, "value": statuts.get(code, 0)}
        for code, libelle in Statut.choices
    ]
    max_statut = max((item["value"] for item in par_statut), default=0)
    for item in par_statut:
        item["percentage"] = round(item["value"] * 100 / max_statut) if max_statut else 0
    conversion = prospections.aggregate(
        total=Count("pk"),
        acceptees=Count("pk", filter=Q(statut=Statut.ACCEPTE)),
    )
    total = conversion["total"]
    acceptees = conversion["acceptees"]
    # Ce taux mesure les prospections créées dans la période qui sont aujourd'hui acceptées,
    # pas les prospections qui ont été acceptées pendant cette période.
    taux_conversion = round(acceptees * 100 / total) if total else 0
    aujourd_hui = timezone.localdate()
    relances_a_venir = Prospection.objects.filter(
        eleve_id__in=eleve_ids,
        statut=Statut.A_RELANCER,
        date_relance__gte=aujourd_hui,
        date_relance__lte=aujourd_hui + timedelta(days=7),
    ).count()
    entreprises = list(
        prospections.values("entreprise__nom")
        .annotate(total=Count("pk"))
        .order_by("-total", "entreprise__nom")[:5]
    )
    max_entreprise = max((item["total"] for item in entreprises), default=0)
    for item in entreprises:
        item["percentage"] = round(item["total"] * 100 / max_entreprise) if max_entreprise else 0
    return {
        "prospections_par_statut": par_statut,
        "taux_conversion": taux_conversion,
        "prospections_total": total,
        "prospections_acceptees": acceptees,
        "relances_a_venir": relances_a_venir,
        "top_entreprises": entreprises,
    }


def calculer_stats_eleve(eleve):
    """Calcule les KPI et graphiques de l'élève sur tout son historique.

    Retourne ses totaux, candidatures envoyées, entretiens, taux de réponse,
    répartition des statuts, activité hebdomadaire et trois relances futures.
    """
    prospections = Prospection.objects.filter(eleve=eleve).select_related("entreprise")
    total = prospections.count()
    candidatures = prospections.filter(statut=Statut.CANDIDATURE_ENVOYEE).count()
    entretiens = prospections.filter(statut=Statut.ENTRETIEN_PROGRAMME).count()
    depassees = prospections.exclude(
        statut__in=(Statut.A_CONTACTER, Statut.TERMINEE)
    ).count()
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


def calculer_stats_superviseur(superviseur, eleves=None, periode="all"):
    """Calcule les KPI du scope actif du superviseur, ou des élèves fournis.

    La période filtre les prospections par date de création ; le résultat
    comprend validation des comptes, entretiens, statuts, activité et inactifs.
    """
    centres_ids = centres_du_superviseur(superviseur)
    if eleves is None:
        eleves = Utilisateur.objects.filter(
            role=Utilisateur.Role.ELEVE, centre_id__in=centres_ids
        ).select_related("centre")
    prospections = filtrer_prospections_periode(
        Prospection.objects.filter(eleve__in=eleves), periode
    )
    nb_eleves = eleves.count()
    valides = eleves.filter(is_valide=True).count()
    entretiens = prospections.filter(statut=Statut.ENTRETIEN_PROGRAMME).count()
    centres = list(Centre.objects.filter(pk__in=centres_ids, utilisateurs__in=eleves).distinct().order_by("nom"))
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


def calculer_stats_admin(eleves=None, superviseurs=None, periode="all"):
    """Calcule les KPI globaux ou ceux des populations fournies.

    La période filtre les prospections et demandes RGPD ; les demandes ouvertes
    depuis plus de 25 jours sont signalées comme en retard.
    """
    if eleves is None:
        eleves = Utilisateur.objects.filter(role=Utilisateur.Role.ELEVE)
    if superviseurs is None:
        superviseurs = Utilisateur.objects.filter(role=Utilisateur.Role.SUPERVISEUR)
    prospections = filtrer_prospections_periode(
        Prospection.objects.filter(eleve__in=eleves), periode
    )
    demandes_ouvertes = DemandeRGPD.objects.filter(
        statut__in=[StatutDemande.RECUE, StatutDemande.EN_COURS]
    ).filter(utilisateur__in=eleves)
    debut = debut_periode_dashboard(periode)
    if debut:
        demandes_ouvertes = demandes_ouvertes.filter(date_demande__date__gte=debut)
    retard = demandes_ouvertes.filter(
        date_demande__lt=timezone.now() - timedelta(days=25)
    ).count()
    repartition = _repartition_statuts(prospections)
    centres = list(Centre.objects.filter(utilisateurs__in=eleves).annotate(
        nombre=Count("utilisateurs", filter=Q(utilisateurs__role=Utilisateur.Role.ELEVE, utilisateurs__in=eleves))
    ).distinct().order_by("nom"))
    demandes_chart = _mois_12(demandes_ouvertes, "date_demande")
    return {
        "kpis": [
            {"label": "Total élèves", "value": eleves.count()},
            {"label": "Total superviseurs", "value": superviseurs.count()},
            {"label": "Total entreprises", "value": prospections.values("entreprise_id").distinct().count()},
            {"label": "Demandes RGPD en attente", "value": demandes_ouvertes.count(), "variant": "danger" if retard else "primary", "detail": f"{retard} en retard (> 25 jours)"},
        ],
        "charts": {
            "prospections_mois": _chart("prospections_mois", "line", "Prospections par mois", *_mois_12(prospections, "date_creation").values()),
            "statuts": _chart("statuts", "doughnut", "Répartition globale des statuts", repartition["labels"], repartition["data"]),
            "centres": _chart("centres", "bar", "Élèves par centre", [centre.nom for centre in centres], [centre.nombre for centre in centres]),
            "demandes_mois": _chart("demandes_mois", "line", "Demandes RGPD par mois", demandes_chart["labels"], demandes_chart["data"]),
        },
        "stats": {"demandes_rgpd_retard": retard},
    }
