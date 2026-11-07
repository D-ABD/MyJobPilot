"""Fonctions de génération des exports du référentiel d'entreprises."""
import csv
import io


COLONNES_ENTREPRISES = (
    "nom",
    "secteur",
    "ville",
    "code_postal",
    "site_web",
    "contact_nom",
    "contact_email",
    "contact_telephone",
    "date_creation",
    "nb_prospections",
)


def exporter_entreprises_csv(entreprises):
    """Retourne un CSV UTF-8 avec BOM à partir des entreprises déjà autorisées."""
    sortie = io.StringIO(newline="")
    writer = csv.DictWriter(sortie, fieldnames=COLONNES_ENTREPRISES, extrasaction="ignore")
    writer.writeheader()
    for entreprise in entreprises:
        writer.writerow({
            "nom": entreprise.nom,
            "secteur": entreprise.secteur,
            "ville": entreprise.ville,
            "code_postal": entreprise.code_postal,
            "site_web": entreprise.site_web,
            "contact_nom": entreprise.contact_nom,
            "contact_email": entreprise.contact_email,
            "contact_telephone": entreprise.contact_telephone,
            "date_creation": entreprise.date_creation.isoformat(),
            "nb_prospections": entreprise.nb_prospections,
        })
    return "\ufeff" + sortie.getvalue()
