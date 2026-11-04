"""Import ligne par ligne des élèves depuis un CSV."""
import csv
import io
import secrets
import string

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from comptes.models import Centre, ConsentementRGPD, Formation, Utilisateur


COLONNES_REQUISES = ("username", "email", "first_name", "last_name", "centre", "formation")


def importer_eleves_csv(fichier):
    texte = io.TextIOWrapper(fichier, encoding="utf-8-sig", newline="")
    lecteur = csv.DictReader(texte)
    if not lecteur.fieldnames or any(col not in lecteur.fieldnames for col in COLONNES_REQUISES):
        return {"total": 0, "crees": 0, "rejetes": 0,
                "erreurs": [{"ligne": 1, "message": "En-tête CSV invalide. Colonnes requises : " + ", ".join(COLONNES_REQUISES)}]}

    total = crees = 0
    erreurs = []
    for numero, ligne in enumerate(lecteur, start=2):
        total += 1
        valeurs = {cle: (ligne.get(cle) or "").strip() for cle in COLONNES_REQUISES}
        raison = None
        centre = None
        formation = None
        try:
            if not valeurs["username"]:
                raise ValueError("username est requis.")
            if Utilisateur.objects.filter(username=valeurs["username"]).exists():
                raise ValueError("username déjà utilisé.")
            try:
                validate_email(valeurs["email"])
            except ValidationError:
                raise ValueError("adresse email invalide.")
            centre = Centre.objects.get(nom=valeurs["centre"])
            formation = Formation.objects.get(centre=centre, nom=valeurs["formation"])
        except Centre.DoesNotExist:
            raison = f"Centre inexistant : {valeurs['centre']}"
        except Formation.DoesNotExist:
            raison = f"Formation inexistante pour le centre {valeurs['centre']} : {valeurs['formation']}"
        except ValueError as exc:
            raison = str(exc)

        if raison:
            erreurs.append({"ligne": numero, "message": raison})
            continue

        mot_de_passe = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        try:
            with transaction.atomic():
                eleve = Utilisateur.objects.create_user(
                    username=valeurs["username"], email=valeurs["email"],
                    first_name=valeurs["first_name"], last_name=valeurs["last_name"],
                    password=mot_de_passe, role=Utilisateur.Role.ELEVE,
                    centre=centre, formation=formation, is_valide=False,
                )
                ConsentementRGPD.objects.create(
                    utilisateur=eleve, version_politique="1.0", ip=None,
                    user_agent="import_csv",
                )
            crees += 1
        except IntegrityError:
            erreurs.append({"ligne": numero, "message": "username déjà utilisé."})

    return {"total": total, "crees": crees, "rejetes": len(erreurs), "erreurs": erreurs}
