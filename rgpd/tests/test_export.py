import json

from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, Utilisateur
from documents.models import Document


class ExportRGPDTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(nom="Centre Paris", defaults={"departement": "75 - Paris"})
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS Test")
        self.user = Utilisateur.objects.create_user(
            username="export_user", password="p", role="eleve", centre=self.centre,
            formation=self.formation, is_valide=True,
        )

    def test_export_json_omet_le_binaire(self):
        Document.objects.create(eleve=self.user, nom="cv.pdf", type="cv", contenu=b"secret", taille=6, content_type="application/pdf")
        self.client.force_login(self.user)
        response = self.client.get(reverse("rgpd:export_rgpd"))
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        payload = json.loads(response.content)
        self.assertEqual(payload["documents"][0]["nom"], "cv.pdf")
        self.assertNotIn("contenu", payload["documents"][0])
        self.assertNotIn(b"secret", response.content)
