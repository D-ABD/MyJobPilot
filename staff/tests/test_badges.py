from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, ScopeSuperviseur, Utilisateur
from core.models import Badge, BadgeObtenu


class BadgesFicheSuperviseurTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre fiche badges", defaults={"departement": "75 - Paris"}
        )
        self.autre_centre = Centre.objects.create(nom="Centre hors fiche badges", departement="69 - Rhône")
        self.formation = Formation.objects.create(centre=self.centre, nom="Formation badges")
        self.eleve = Utilisateur.objects.create_user(
            username="fiche-badges-eleve", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.centre, formation=self.formation, is_valide=True,
        )
        self.hors_scope = Utilisateur.objects.create_user(
            username="fiche-badges-hors", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.autre_centre, is_valide=True,
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="fiche-badges-superviseur", password="test",
            role=Utilisateur.Role.SUPERVISEUR, centre=self.centre, is_staff=True,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre)

    def test_superviseur_voit_points_et_badges_de_leleve_dans_son_scope(self):
        badge = Badge.objects.create(
            slug="fiche-superviseur-badge", categorie=Badge.Categorie.PROSPECTION,
            nom="Badge scope", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            valeur_points=30,
        )
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        self.client.force_login(self.superviseur)

        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "30 points")
        self.assertContains(response, "1/18 badges")
        self.assertContains(response, "Badge scope")

    def test_superviseur_hors_scope_recoit_403_sur_fiche_badges(self):
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("staff:detail_eleve", args=[self.hors_scope.pk]))
        self.assertEqual(response.status_code, 403)

    def test_detail_eleve_superviseur_affiche_niveau_et_xp(self):
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Niveau : Novice")
        self.assertContains(response, "0 XP")
