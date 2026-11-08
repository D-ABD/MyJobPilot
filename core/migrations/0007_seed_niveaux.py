from django.db import migrations


NIVEAUX = (
    ("Novice", 0, 1),
    ("Explorateur", 100, 2),
    ("Persévérant", 250, 3),
    ("Chasseur", 500, 4),
    ("Stratège", 1000, 5),
    ("Expert", 2000, 6),
    ("Ambassadeur", 4000, 7),
)


def seed_niveaux(apps, schema_editor):
    Niveau = apps.get_model("core", "Niveau")
    db = schema_editor.connection.alias
    for nom, seuil_min, ordre_affichage in NIVEAUX:
        Niveau.objects.using(db).get_or_create(
            nom=nom,
            defaults={
                "seuil_min": seuil_min,
                "ordre_affichage": ordre_affichage,
                "est_actif": True,
            },
        )


def unseed_niveaux(apps, schema_editor):
    Niveau = apps.get_model("core", "Niveau")
    db = schema_editor.connection.alias
    Niveau.objects.using(db).filter(nom__in=[niveau[0] for niveau in NIVEAUX]).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0006_niveau")]

    operations = [migrations.RunPython(seed_niveaux, unseed_niveaux)]
