from django.test import TestCase

from comptes.models import Centre, Formation, Utilisateur
from documents.models import Document, TypeDocument


class DocumentModelTests(TestCase):
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
            username="document_model",
            password="test-password",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def test_document_enregistre_son_eleve_et_son_type(self):
        document = Document.objects.create(
            eleve=self.eleve,
            nom="CV",
            contenu=b"contenu",
            taille=8,
            content_type="application/pdf",
            type=TypeDocument.CV,
        )
        self.assertEqual(document.eleve, self.eleve)
        self.assertEqual(document.get_type_display(), "CV")

    def test_listing_differe_le_champ_binaire(self):
        document = Document.objects.create(
            eleve=self.eleve,
            nom="Lettre",
            contenu=b"secret",
            taille=6,
            content_type="text/plain",
        )
        ligne = Document.objects.listing().get(pk=document.pk)
        self.assertIn("contenu", ligne.get_deferred_fields())
        self.assertEqual(ligne.nom, "Lettre")
