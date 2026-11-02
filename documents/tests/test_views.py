from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, JournalAction, ScopeSuperviseur, Utilisateur
from documents.models import Document


class DocumentViewsTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.autre_centre, _ = Centre.objects.get_or_create(
            nom="Centre Lyon",
            defaults={"departement": "69 - Rhône"},
        )
        self.formation, _ = Formation.objects.get_or_create(
            centre=self.centre,
            nom="BTS SIO",
        )
        self.autre_formation, _ = Formation.objects.get_or_create(
            centre=self.autre_centre,
            nom="BTS SIO",
        )
        self.eleve = self.creer_utilisateur(
            "document_eleve", Utilisateur.Role.ELEVE, self.centre, self.formation
        )
        self.autre_eleve = self.creer_utilisateur(
            "document_autre",
            Utilisateur.Role.ELEVE,
            self.autre_centre,
            self.autre_formation,
        )
        self.superviseur = self.creer_utilisateur(
            "document_superviseur",
            Utilisateur.Role.SUPERVISEUR,
            self.centre,
            self.formation,
        )
        self.admin = self.creer_utilisateur(
            "document_admin",
            Utilisateur.Role.ADMIN,
            self.centre,
            self.formation,
            is_staff=True,
            is_superuser=True,
        )

    def creer_utilisateur(self, username, role, centre, formation, **extra):
        return Utilisateur.objects.create_user(
            username=username,
            password="test-password",
            role=role,
            centre=centre,
            formation=formation,
            is_valide=True,
            **extra,
        )

    def creer_document(self, eleve=None, nom="CV", contenu=b"pdf"):
        return Document.objects.create(
            eleve=eleve or self.eleve,
            nom=nom,
            type="cv",
            contenu=contenu,
            taille=len(contenu),
            content_type="application/pdf",
        )

    def test_liste_eleve_ne_contient_que_ses_documents(self):
        son_document = self.creer_document()
        self.creer_document(self.autre_eleve, "Privé")
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("documents:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["documents"]), [son_document])

    def test_envoi_cree_document_et_journalise(self):
        self.client.force_login(self.eleve)
        response = self.client.post(
            reverse("documents:upload"),
            {
                "nom": "CV Abd",
                "type": "cv",
                "contenu": SimpleUploadedFile(
                    "cv.pdf",
                    b"%PDF-content",
                    content_type="application/pdf",
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(eleve=self.eleve, nom="CV Abd")
        self.assertEqual(document.contenu, b"%PDF-content")
        self.assertTrue(
            JournalAction.objects.filter(
                action=JournalAction.Action.DOCUMENT_UPLOAD,
                cible_id=str(document.pk),
            ).exists()
        )

    def test_telechargement_proprietaire_retourne_le_binaire_et_journalise(self):
        document = self.creer_document()
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("documents:download", args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"pdf")
        self.assertTrue(
            JournalAction.objects.filter(
                action=JournalAction.Action.DOCUMENT_DOWNLOAD,
                cible_id=str(document.pk),
            ).exists()
        )

    def test_un_eleve_ne_peut_pas_telecharger_le_document_d_un_autre(self):
        document = self.creer_document(self.autre_eleve)
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("documents:download", args=[document.pk]))
        self.assertEqual(response.status_code, 403)

    def test_admin_peut_telecharger_un_document(self):
        document = self.creer_document(self.autre_eleve)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("documents:download", args=[document.pk]))
        self.assertEqual(response.status_code, 200)

    def test_superviseur_peut_telecharger_dans_son_scope(self):
        ScopeSuperviseur.objects.create(
            superviseur=self.superviseur,
            centre=self.centre,
            is_active=True,
        )
        document = self.creer_document()
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("documents:download", args=[document.pk]))
        self.assertEqual(response.status_code, 200)

    def test_superviseur_hors_scope_ne_peut_pas_telecharger(self):
        document = self.creer_document(self.autre_eleve)
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("documents:download", args=[document.pk]))
        self.assertEqual(response.status_code, 403)

    def test_suppression_eleve_journalisee(self):
        document = self.creer_document()
        self.client.force_login(self.eleve)
        response = self.client.post(reverse("documents:delete", args=[document.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())
        self.assertTrue(
            JournalAction.objects.filter(
                action=JournalAction.Action.DOCUMENT_SUPPRIME,
                cible_id=str(document.pk),
            ).exists()
        )

    def test_superviseur_ne_peut_pas_supprimer(self):
        ScopeSuperviseur.objects.create(
            superviseur=self.superviseur,
            centre=self.centre,
            is_active=True,
        )
        document = self.creer_document()
        self.client.force_login(self.superviseur)
        response = self.client.post(reverse("documents:delete", args=[document.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Document.objects.filter(pk=document.pk).exists())

    def test_staff_consulte_uniquement_les_documents_du_scope(self):
        ScopeSuperviseur.objects.create(
            superviseur=self.superviseur,
            centre=self.centre,
            is_active=True,
        )
        document = self.creer_document()
        self.creer_document(self.autre_eleve, "Hors scope")
        self.client.force_login(self.superviseur)
        response = self.client.get(
            reverse("staff:documents_eleve", args=[self.eleve.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["documents"]), [document])

    def test_staff_hors_scope_et_eleve_refuses(self):
        self.client.force_login(self.superviseur)
        hors_scope = self.client.get(
            reverse("staff:documents_eleve", args=[self.autre_eleve.pk])
        )
        self.assertEqual(hors_scope.status_code, 403)
        self.client.force_login(self.eleve)
        interdit = self.client.get(
            reverse("staff:documents_eleve", args=[self.eleve.pk])
        )
        self.assertEqual(interdit.status_code, 403)

    def test_admin_consulte_les_documents_de_tout_eleve(self):
        document = self.creer_document(self.autre_eleve)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("staff:documents_eleve", args=[self.autre_eleve.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["documents"]), [document])
