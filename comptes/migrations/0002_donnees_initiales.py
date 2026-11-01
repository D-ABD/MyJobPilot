"""Crée les centres et formations de démonstration."""
from django.db import migrations


def creer_referentiels(apps, schema_editor):
    Centre = apps.get_model("comptes", "Centre")
    Formation = apps.get_model("comptes", "Formation")
    centres = {
        "Centre Paris": "75 - Paris",
        "Centre Lyon": "69 - Rhône",
    }
    objets_centres = {}
    for nom, departement in centres.items():
        objets_centres[nom], _ = Centre.objects.using(schema_editor.connection.alias).get_or_create(
            nom=nom,
            defaults={"departement": departement},
        )
    formations = (
        ("BTS SIO", "Centre Paris"),
        ("BTS Communication", "Centre Paris"),
        ("BUT Informatique", "Centre Lyon"),
        ("BTS GPME", "Centre Lyon"),
    )
    for nom, centre_nom in formations:
        Formation.objects.using(schema_editor.connection.alias).get_or_create(
            centre=objets_centres[centre_nom],
            nom=nom,
        )


def supprimer_referentiels(apps, schema_editor):
    Centre = apps.get_model("comptes", "Centre")
    Formation = apps.get_model("comptes", "Formation")
    alias = schema_editor.connection.alias
    noms_formations = ("BTS SIO", "BTS Communication", "BUT Informatique", "BTS GPME")
    Formation.objects.using(alias).filter(nom__in=noms_formations).delete()
    Centre.objects.using(alias).filter(nom__in=("Centre Paris", "Centre Lyon")).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("comptes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(creer_referentiels, supprimer_referentiels),
    ]
