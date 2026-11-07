"""Import du référentiel d'entreprises depuis un fichier CSV."""
import csv
import io
import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError, transaction

from comptes.models import JournalAction

from .models import Entreprise


CHAMPS_CSV = (
    "nom", "secteur", "ville", "code_postal", "site_web",
    "contact_nom", "contact_email", "contact_telephone",
)
VALIDER_URL = URLValidator(schemes=["http", "https"])
MOTIF_CODE_POSTAL = re.compile(r"^[A-Z0-9][A-Z0-9 \-]{2,9}$", re.IGNORECASE)


def _valider_ligne(ligne):
    """Nettoie et valide les champs d'une ligne, ou renvoie sa première erreur."""
    valeurs = {champ: (ligne.get(champ) or "").strip() for champ in CHAMPS_CSV}
    if not valeurs["nom"]:
        return None, "Nom obligatoire"
    if len(valeurs["nom"]) > 200:
        return None, "Nom trop long (200 caractères maximum)"
    if Entreprise.objects.filter(nom__iexact=valeurs["nom"]).exists():
        return None, "Nom déjà utilisé"

    longueurs = {
        "secteur": 100,
        "ville": 100,
        "code_postal": 20,
        "site_web": 200,
        "contact_nom": 100,
        "contact_email": 254,
        "contact_telephone": 30,
    }
    for champ, maximum in longueurs.items():
        if len(valeurs[champ]) > maximum:
            return None, f"{champ} dépasse {maximum} caractères"

    if valeurs["contact_email"]:
        try:
            validate_email(valeurs["contact_email"])
        except ValidationError:
            return None, "Email invalide"
    if valeurs["site_web"]:
        try:
            VALIDER_URL(valeurs["site_web"])
        except ValidationError:
            return None, "URL invalide"
    if valeurs["code_postal"]:
        valeurs["code_postal"] = valeurs["code_postal"].upper()
        if not MOTIF_CODE_POSTAL.fullmatch(valeurs["code_postal"]):
            return None, "Code postal invalide"
    return valeurs, None


def importer_entreprises_csv(fichier, auteur) -> dict:
    """Importe les lignes valides et retourne le bilan avec les erreurs par ligne."""
    contenu = fichier.read()
    if isinstance(contenu, bytes):
        contenu = contenu.decode("utf-8-sig")
    else:
        contenu = contenu.lstrip("\ufeff")

    lecteur = csv.DictReader(io.StringIO(contenu, newline=""))
    en_tetes = [entete.strip().lower() if entete else "" for entete in (lecteur.fieldnames or [])]
    if "nom" not in en_tetes:
        rapport = {
            "total": 0,
            "crees": 0,
            "rejetes": 1,
            "erreurs": [{"ligne": 1, "raison": "Colonne obligatoire 'nom' absente"}],
        }
    else:
        lecteur.fieldnames = en_tetes
        rapport = {"total": 0, "crees": 0, "rejetes": 0, "erreurs": []}
        for numero_ligne, ligne in enumerate(lecteur, start=2):
            rapport["total"] += 1
            valeurs, raison = _valider_ligne(ligne)
            if raison:
                rapport["rejetes"] += 1
                rapport["erreurs"].append({"ligne": numero_ligne, "raison": raison})
                continue
            try:
                with transaction.atomic():
                    Entreprise.objects.create(**valeurs)
                rapport["crees"] += 1
            except IntegrityError:
                rapport["rejetes"] += 1
                rapport["erreurs"].append({"ligne": numero_ligne, "raison": "Nom déjà utilisé"})

    JournalAction.objects.create(
        utilisateur=auteur,
        action=JournalAction.Action.IMPORT_CSV,
        cible_type="Entreprise",
        details={
            "type": "entreprises",
            "total": rapport["total"],
            "crees": rapport["crees"],
            "rejetes": rapport["rejetes"],
        },
    )
    return rapport
