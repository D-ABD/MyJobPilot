from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from comptes.models import Centre, Formation, Utilisateur
from documents.forms import DocumentUploadForm
from documents.models import Document


class DocumentQuotaTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(
            centre=self.centre,
            nom="BTS SIO",
        )
        self.eleve = Utilisateur.objects.create_user(
            username="document_quota",
            password="test-password",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def form(self, taille):
        fichier = SimpleUploadedFile(
            "document.pdf",
            b"x" * taille,
            content_type="application/pdf",
        )
        return DocumentUploadForm(
            {"nom": "Document", "type": "autre"},
            {"contenu": fichier},
            eleve=self.eleve,
        )

    def test_refuse_un_fichier_superieur_a_cinq_mo(self):
        form = self.form(settings.DOCUMENT_MAX_SIZE_BYTES + 1)
        self.assertFalse(form.is_valid())
        self.assertIn("contenu", form.errors)

    def test_accepte_un_fichier_egal_a_la_limite(self):
        form = self.form(settings.DOCUMENT_MAX_SIZE_BYTES)
        self.assertTrue(form.is_valid(), form.errors)

    def test_refuse_un_envoi_qui_depasse_le_quota_et_indique_le_restant(self):
        quota = settings.DOCUMENT_QUOTA_BYTES
        Document.objects.create(
            eleve=self.eleve,
            nom="Déjà présent",
            contenu=b"x",
            taille=quota - 10,
            content_type="application/octet-stream",
        )
        form = self.form(11)
        self.assertFalse(form.is_valid())
        self.assertIn("Quota dépassé", str(form.errors))
        self.assertIn("reste", str(form.errors))

    def test_accepte_un_envoi_qui_atteint_exactement_le_quota(self):
        quota = settings.DOCUMENT_QUOTA_BYTES
        Document.objects.create(
            eleve=self.eleve,
            nom="Déjà présent",
            contenu=b"x",
            taille=quota - 10,
            content_type="application/octet-stream",
        )
        form = self.form(10)
        self.assertTrue(form.is_valid(), form.errors)
