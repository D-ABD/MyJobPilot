from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, Utilisateur
from core.models import Badge, BadgeObtenu


class BadgesFicheAdminTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre fiche badges admin", defaults={"departement": "75 - Paris"}
        )
        self.formation = Formation.objects.create(centre=self.centre, nom="Formation admin badges")
        self.eleve = Utilisateur.objects.create_user(
            username="fiche-badges-admin-eleve", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.centre, formation=self.formation, is_valide=True,
        )
        self.admin = Utilisateur.objects.create_user(
            username="fiche-badges-admin", password="test", role=Utilisateur.Role.ADMIN,
            is_staff=True,
        )

    def test_admin_voit_points_et_badges_dans_la_fiche_eleve(self):
        badge = Badge.objects.create(
            slug="fiche-admin-badge", categorie=Badge.Categorie.SUIVI,
            nom="Badge admin", type_condition=Badge.TypeCondition.RELANCES_COUNT,
            valeur_points=15,
        )
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin_dashboard:eleve_detail", args=[self.eleve.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "15 points")
        self.assertContains(response, "1/18 badges")
        self.assertContains(response, "Badge admin")

    def test_fiche_eleve_admin_affiche_niveau_et_xp(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:eleve_detail", args=[self.eleve.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Niveau : Novice")
        self.assertContains(response, "0 XP")
