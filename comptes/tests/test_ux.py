from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from comptes.models import Centre, Formation
from myjobpilot.views import page_404


Utilisateur = get_user_model()


class ExperienceUtilisateurTests(TestCase):
    def test_page_404_affiche_le_template_personnalise(self):
        request = RequestFactory().get("/page-inconnue/")
        request.user = AnonymousUser()

        response = page_404(request)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page non trouvée (404)", status_code=404)
        self.assertContains(response, "Retour à l'accueil")

    def test_mon_compte_affiche_les_informations_et_liens_eleve(self):
        centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        formation, _ = Formation.objects.get_or_create(
            centre=centre,
            nom="Formation test",
        )
        utilisateur = Utilisateur.objects.create_user(
            username="profil_eleve",
            password="test-password-123",
            email="profil@example.com",
            first_name="Jean",
            last_name="Dupont",
            role=Utilisateur.Role.ELEVE,
            centre=centre,
            formation=formation,
            is_valide=True,
        )
        self.client.force_login(utilisateur)

        response = self.client.get(reverse("comptes:mon_compte"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "profil_eleve")
        self.assertContains(response, "Mes documents")
        self.assertContains(response, "Mes demandes RGPD")
        self.assertContains(response, "Exporter mes données RGPD")
