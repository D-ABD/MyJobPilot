"""Accès à l'API officielle La bonne alternance."""
import hashlib
import logging
import os
import re

import requests
from django.core.cache import cache


BASE_URL = "https://api.apprentissage.beta.gouv.fr/api"
CACHE_TIMEOUT = 60 * 60
REQUEST_TIMEOUT = 8
_CODE_ROME = re.compile(r"^[A-Z]\d{4}$", re.IGNORECASE)
_CODE_POSTAL = re.compile(r"^\d{5}$")
logger = logging.getLogger(__name__)


def _headers():
    cle_api = os.getenv("LBA_API_KEY", "")
    return {"Authorization": f"Bearer {cle_api}"} if cle_api else {}


def _get_json(endpoint, params=None):
    """Effectue un GET avec la clé configurée et transforme les erreurs en absence de résultat."""
    try:
        response = requests.get(
            f"{BASE_URL}/{endpoint.lstrip('/')}",
            params=params or {},
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("Échec de l'appel La bonne alternance (%s): %s", endpoint, exc)
        return None


def _coordonnees_code_postal(code_postal):
    cle_cache = f"lba:commune:{code_postal}"
    coordonnees = cache.get(cle_cache)
    if coordonnees is not None:
        return coordonnees

    communes = _get_json("geographie/v1/commune/search", {"code": code_postal})
    if not isinstance(communes, list) or not communes:
        return None
    point = communes[0].get("localisation", {}).get("centre", {})
    coords = point.get("coordinates", [])
    if len(coords) < 2:
        return None
    # GeoJSON expose les coordonnées dans l'ordre longitude, latitude.
    coordonnees = {"longitude": coords[0], "latitude": coords[1]}
    cache.set(cle_cache, coordonnees, CACHE_TIMEOUT)
    return coordonnees


def _valeur(objet, *chemin, default=""):
    courant = objet
    for cle in chemin:
        if not isinstance(courant, dict):
            return default
        courant = courant.get(cle)
    return courant if courant is not None else default


def _ville_opportunite(opportunite):
    ville = (
        _valeur(opportunite, "location", "city")
        or _valeur(opportunite, "location", "ville")
        or _valeur(opportunite, "workplace", "location", "city")
    )
    if ville:
        return str(ville)
    adresse = _valeur(opportunite, "location", "address")
    if isinstance(adresse, dict):
        ville = adresse.get("city") or adresse.get("ville") or adresse.get("label")
        if ville:
            return str(ville)
        adresse = adresse.get("address", "")
    if isinstance(adresse, str):
        correspondance = re.search(r"\b\d{5}\s+([^,]+)", adresse)
        if correspondance:
            return correspondance.group(1).strip()
        return adresse.strip()
    return ""


def _identifiant_opportunite(opportunite):
    identifiant = opportunite.get("identifier", {})
    if isinstance(identifiant, dict):
        valeur = identifiant.get("id")
        if valeur:
            return str(valeur)
        partner_id = identifiant.get("partner_job_id")
        partner = identifiant.get("partner_label", "")
        if partner_id:
            return f"{partner}:{partner_id}"
    valeur = opportunite.get("id")
    return str(valeur) if valeur else ""


def _dedoublonner_opportunites(opportunites):
    uniques = []
    identifiants = set()
    for opportunite in opportunites:
        identifiant = _identifiant_opportunite(opportunite)
        if identifiant and identifiant in identifiants:
            continue
        if identifiant:
            identifiants.add(identifiant)
        uniques.append(opportunite)
    return uniques


def _normaliser_offre(offre):
    rome_codes = _valeur(offre, "offer", "rome_codes", default=None)
    if rome_codes is None:
        rome_codes = _valeur(offre, "rome_codes", default=[])
    publication_creation = (
        _valeur(offre, "offer", "publication", "creation", default=None)
        or _valeur(offre, "publication", "creation", default=None)
    )
    return {
        "_id": _identifiant_opportunite(offre),
        "_rome_codes": [str(code).upper() for code in rome_codes] if isinstance(rome_codes, list) else [],
        "_publication_creation": publication_creation,
        "titre": (
            _valeur(offre, "offer", "title")
            or _valeur(offre, "offer", "label")
            or _valeur(offre, "offer", "name")
            or "Offre d'alternance"
        ),
        "entreprise": _valeur(offre, "workplace", "name") or "Entreprise non renseignée",
        "ville": _ville_opportunite(offre),
        "url": _valeur(offre, "url") or _valeur(offre, "apply", "url"),
    }


def _normaliser_entreprise(entreprise):
    domaine = entreprise.get("domain", {})
    if isinstance(domaine, dict):
        secteur = domaine.get("label") or domaine.get("naf_label") or domaine.get("naf") or ""
        if isinstance(secteur, dict):
            secteur = secteur.get("label") or secteur.get("code") or ""
    else:
        secteur = str(domaine or "")
    return {
        "_id": _identifiant_opportunite(entreprise),
        "nom": _valeur(entreprise, "workplace", "name") or "Entreprise non renseignée",
        "secteur": str(secteur),
        "ville": _ville_opportunite(entreprise),
    }


def _rechercher_opportunites_lba(romes, ville, rayon):
    """Récupère et met en cache les résultats communs jobs/recruteurs pendant une heure."""
    if not isinstance(ville, str) or not _CODE_POSTAL.fullmatch(ville.strip()):
        return None
    try:
        rayon = int(rayon)
    except (TypeError, ValueError):
        return None
    if not 0 <= rayon <= 200:
        return None

    ville = ville.strip()
    codes_rome = [code.strip().upper() for code in str(romes or "").split(",") if code.strip()]
    if len(codes_rome) > 3 or any(not _CODE_ROME.fullmatch(code) for code in codes_rome):
        return None
    romes_normalises = ",".join(codes_rome)
    empreinte = hashlib.sha256(f"{romes_normalises}:{ville}:{rayon}".encode("utf-8")).hexdigest()
    cle_cache = f"lba:opportunites:{empreinte}"
    resultat_cache = cache.get(cle_cache)
    if resultat_cache is not None:
        return resultat_cache

    coordonnees = _coordonnees_code_postal(ville)
    if not coordonnees:
        return None
    params = {
        "latitude": coordonnees["latitude"],
        "longitude": coordonnees["longitude"],
        "radius": rayon,
    }
    if romes_normalises:
        params["romes"] = romes_normalises
    donnees = _get_json("job/v1/search", params)
    if not isinstance(donnees, dict):
        return None

    offres_brutes = _dedoublonner_opportunites(
        [offre for offre in donnees.get("jobs", []) if isinstance(offre, dict)]
    )
    entreprises_brutes = _dedoublonner_opportunites(
        [entreprise for entreprise in donnees.get("recruiters", []) if isinstance(entreprise, dict)]
    )
    offres = [_normaliser_offre(offre) for offre in offres_brutes]
    entreprises = [
        _normaliser_entreprise(entreprise)
        for entreprise in entreprises_brutes
    ]
    resultat = {"offres": offres, "entreprises": entreprises}
    cache.set(cle_cache, resultat, CACHE_TIMEOUT)
    return resultat


def rechercher_offres_lba(romes, ville, rayon):
    """Recherche les offres actives à proximité d'un code postal et pour des codes ROME."""
    resultats = _rechercher_opportunites_lba(romes, ville, rayon)
    if resultats is None:
        return []
    return resultats["offres"]


def rechercher_entreprises_lba(romes, ville, rayon):
    """Recherche les recruteurs à fort potentiel pour les candidatures spontanées."""
    resultats = _rechercher_opportunites_lba(romes, ville, rayon)
    if resultats is None:
        return []
    return resultats["entreprises"]
