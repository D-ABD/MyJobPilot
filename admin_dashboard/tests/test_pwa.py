from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, Utilisateur


class PWATests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris", defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS PWA")
        self.admin = Utilisateur.objects.create_user(
            username="admin_pwa", password="p", role=Utilisateur.Role.ADMIN,
        )
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_pwa", password="p", role=Utilisateur.Role.ELEVE,
            centre=self.centre, formation=self.formation, is_valide=True,
        )

    def test_manifest_accessible(self):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_sw_js_accessible(self):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")

    def test_offline_accessible(self):
        response = self.client.get(reverse("offline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vous êtes hors ligne")

    def test_templates_ont_classes_responsive(self):
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertContains(response, "table-responsive")
