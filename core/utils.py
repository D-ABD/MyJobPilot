"""Utilitaires partagés par les vues et modèles du projet."""
import re


_ESPACES_UNICODE = "\u00a0\u202f\u2007\u2009\u200a\u2028\u2029"
_TABLE_TRADUCTION = str.maketrans({caractere: " " for caractere in _ESPACES_UNICODE})
_CARACTERES_CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f]")

# Les caractères de contrôle sont explicitement interdits, même si certains
# correspondent à \s en Python (par exemple tabulation et retour à la ligne).
_MOTIF_CODES_ROME = re.compile(
    r"\A(?!.*[\x00-\x1f\x7f-\x9f])[A-Z]\d{4}(?:[ ]*,[ ]*[A-Z]\d{4})*\Z"
)


def normaliser_codes_rome(valeur: str) -> str:
    """Normalise les espaces Unicode et retire le BOM des codes ROME."""
    valeur = (valeur or "").replace("\ufeff", "")
    valeur = valeur.translate(_TABLE_TRADUCTION)
    # str.strip() effacerait les tabulations et autres contrôles périphériques.
    # Les garder permet au validateur de rejeter toute saisie contenant un contrôle.
    if _CARACTERES_CONTROLE.search(valeur):
        return valeur
    return valeur.strip()
