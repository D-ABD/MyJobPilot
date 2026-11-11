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
    """Normalise les espaces de saisie des codes ROME sans valider leur format.

    Remplace U+00A0, U+202F, U+2007, U+2009, U+200A, U+2028 et U+2029 par
    des espaces ASCII, retire U+FEFF et conserve les caractères de contrôle
    pour que la validation ultérieure les rejette.
    """
    valeur = (valeur or "").replace("\ufeff", "")
    valeur = valeur.translate(_TABLE_TRADUCTION)
    # str.strip() effacerait les tabulations et autres contrôles périphériques.
    # Les garder permet au validateur de rejeter toute saisie contenant un contrôle.
    if _CARACTERES_CONTROLE.search(valeur):
        return valeur
    return valeur.strip()
