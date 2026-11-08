from django.db import migrations


BADGES = (
    ("prospection-10", "prospection", "Novice", "prospections_contactees_count", 10, 1),
    ("prospection-20", "prospection", "Explorateur", "prospections_contactees_count", 20, 2),
    ("prospection-35", "prospection", "Persévérant", "prospections_contactees_count", 35, 3),
    ("prospection-50", "prospection", "Chasseur", "prospections_contactees_count", 50, 4),
    ("prospection-75", "prospection", "Stratège", "prospections_contactees_count", 75, 5),
    ("prospection-100", "prospection", "Expert", "prospections_contactees_count", 100, 6),
    ("candidature-3", "candidature", "Premier pas", "candidatures_count", 3, 1),
    ("candidature-5", "candidature", "Candidat motivé", "candidatures_count", 5, 2),
    ("candidature-10", "candidature", "Candidat engagé", "candidatures_count", 10, 3),
    ("candidature-15", "candidature", "Candidat déterminé", "candidatures_count", 15, 4),
    ("candidature-25", "candidature", "Candidat confirmé", "candidatures_count", 25, 5),
    ("relance-1", "suivi", "Premier suivi", "relances_count", 1, 1),
    ("relance-3", "suivi", "Relanceur", "relances_count", 3, 2),
    ("relance-5", "suivi", "Insistant", "relances_count", 5, 3),
    ("relance-10", "suivi", "Persévérant", "relances_count", 10, 4),
    ("relance-15", "suivi", "Accrocheur", "relances_count", 15, 5),
    ("relance-25", "suivi", "Roi de la relance", "relances_count", 25, 6),
)


def seed_badges(apps, schema_editor):
    Badge = apps.get_model("core", "Badge")
    db = schema_editor.connection.alias
    for slug, categorie, nom, type_condition, seuil, ordre in BADGES:
        Badge.objects.using(db).get_or_create(
            slug=slug,
            defaults={
                "categorie": categorie,
                "nom": nom,
                "type_condition": type_condition,
                "seuil": seuil,
                "ordre_affichage": ordre,
                "valeur_points": 10,
                "description": "",
                "icone": "",
                "est_actif": True,
            },
        )


def unseed_badges(apps, schema_editor):
    Badge = apps.get_model("core", "Badge")
    BadgeObtenu = apps.get_model("core", "BadgeObtenu")
    db = schema_editor.connection.alias
    slugs = [badge[0] for badge in BADGES]
    badges = Badge.objects.using(db).filter(slug__in=slugs)
    if BadgeObtenu.objects.using(db).filter(badge__in=badges).exists():
        raise RuntimeError(
            "Impossible d'annuler les badges initiaux : au moins un badge a déjà été obtenu."
        )
    badges.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_badge_badgeobtenu"),
    ]

    operations = [
        migrations.RunPython(seed_badges, unseed_badges),
    ]
