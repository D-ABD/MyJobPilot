from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, ScopeSuperviseur, Utilisateur
from documents.models import Document
from entreprises.models import Entreprise, Prospection


class RechercheGlobaleTests(TestCase):
    def setUp(self):
        self.centre_paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.centre_lyon, _ = Centre.objects.get_or_create(
            nom="Centre Lyon",
            defaults={"departement": "69 - Rhône"},
        )
        self.eleve = self.creer_utilisateur(
            "eleve_recherche_14", Utilisateur.Role.ELEVE,
            self.centre_paris, "jean.durand@example.com", "Jean", "Durand",
        )
        self.eleve_scope = self.creer_utilisateur(
            "scope_recherche_14", Utilisateur.Role.ELEVE,
            self.centre_paris, "scope.eleve@example.com", "Sophie", "Scope",
        )
        self.eleve_hors_scope = self.creer_utilisateur(
            "hors_scope_recherche_14", Utilisateur.Role.ELEVE,
            self.centre_lyon, "hors.scope@example.com", "Alex", "Autre",
        )
        self.superviseur = self.creer_utilisateur(
            "superviseur_recherche_14", Utilisateur.Role.SUPERVISEUR,
            self.centre_paris, "superviseur@example.com",
        )
        self.admin = self.creer_utilisateur(
            "admin_recherche_14", Utilisateur.Role.ADMIN,
            None, "admin@example.com",
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)

    def creer_utilisateur(self, username, role, centre, email, first_name="", last_name=""):
        return Utilisateur.objects.create_user(
            username=username,
            password="MotDePasseRecherche14!",
            role=role,
            centre=centre,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_valide=True,
        )

    def creer_prospection(self, eleve, nom):
        entreprise = Entreprise.objects.create(nom=nom)
        return Prospection.objects.create(eleve=eleve, entreprise=entreprise)

    def creer_document(self, eleve, nom):
        return Document.objects.create(
            eleve=eleve,
            nom=nom,
            contenu=b"contenu-test",
            taille=len(b"contenu-test"),
            content_type="text/plain",
        )

    def rechercher(self, user, q):
        self.client.force_login(user)
        return self.client.get(reverse("core:recherche"), {"q": q})

    def test_recherche_prospection_eleve(self):
        self.creer_prospection(self.eleve, "Acme Offre Élève")
        self.creer_prospection(self.eleve_scope, "Acme Offre Scope")

        response = self.rechercher(self.eleve, "Acme Offre")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["prospections"]), 1)
        self.assertContains(response, "Acme Offre Élève")
        self.assertNotContains(response, "Acme Offre Scope")

    def test_recherche_prospection_superviseur(self):
        self.creer_prospection(self.superviseur, "Scope Offre Superviseur")
        self.creer_prospection(self.eleve_scope, "Scope Offre Élève")
        self.creer_prospection(self.eleve_hors_scope, "Scope Offre Hors périmètre")

        response = self.rechercher(self.superviseur, "Scope Offre")

        self.assertEqual(len(response.context["prospections"]), 2)
        self.assertContains(response, "Scope Offre Superviseur")
        self.assertContains(response, "Scope Offre Élève")
        self.assertNotContains(response, "Scope Offre Hors périmètre")

    def test_recherche_prospection_admin(self):
        self.creer_prospection(self.eleve, "Admin Offre Paris")
        self.creer_prospection(self.eleve_hors_scope, "Admin Offre Lyon")

        response = self.rechercher(self.admin, "Admin Offre")

        self.assertEqual(len(response.context["prospections"]), 2)

    def test_recherche_document_eleve(self):
        self.creer_document(self.eleve, "CV Recherche Élève.pdf")
        self.creer_document(self.eleve_scope, "CV Recherche Scope.pdf")

        response = self.rechercher(self.eleve, "CV Recherche")

        self.assertEqual(len(response.context["documents"]), 1)
        self.assertContains(response, "CV Recherche Élève.pdf")
        self.assertNotContains(response, "CV Recherche Scope.pdf")

    def test_recherche_document_superviseur_scope(self):
        self.creer_document(self.superviseur, "Document Scope Propre.pdf")
        self.creer_document(self.eleve_scope, "Document Scope Élève.pdf")
        self.creer_document(self.eleve_hors_scope, "Document Scope Externe.pdf")

        response = self.rechercher(self.superviseur, "Document Scope")

        self.assertEqual(len(response.context["documents"]), 2)
        self.assertNotContains(response, "Document Scope Externe.pdf")

    def test_recherche_document_admin(self):
        self.creer_document(self.eleve, "Document Admin Paris.pdf")
        self.creer_document(self.eleve_hors_scope, "Document Admin Lyon.pdf")

        response = self.rechercher(self.admin, "Document Admin")

        self.assertEqual(len(response.context["documents"]), 2)

    def test_recherche_eleve_admin(self):
        response = self.rechercher(self.admin, "jean.durand@example.com")

        self.assertEqual(len(response.context["eleves"]), 1)
        self.assertContains(response, self.eleve.username)
        self.assertContains(response, "Jean Durand")
        self.assertNotContains(response, self.eleve.email)
        self.assertNotIn("email", response.context["eleves"][0])

    def test_recherche_eleve_superviseur(self):
        response = self.rechercher(self.superviseur, "scope.eleve@example.com")

        self.assertEqual(len(response.context["eleves"]), 1)
        self.assertContains(response, self.eleve_scope.username)
        self.assertNotContains(response, self.eleve_scope.email)
        self.assertNotContains(response, self.eleve_hors_scope.username)

    def test_recherche_eleve_eleve(self):
        response = self.rechercher(self.eleve, "scope.eleve@example.com")

        self.assertEqual(response.context["eleves"], [])
        self.assertContains(response, "Aucun résultat")
        self.assertNotContains(response, self.eleve_scope.username)

    def test_recherche_q_vide(self):
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("core:recherche"), {"q": "   "})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saisissez un terme de recherche pour commencer.")

    def test_recherche_non_authentifie(self):
        response = self.client.get(reverse("core:recherche"), {"q": "ACME"})

        self.assertRedirects(response, f"{reverse('comptes:connexion')}?next=/recherche/?q=ACME")

    def test_recherche_accent_insensible(self):
        self.creer_prospection(self.eleve, "Ecole Écho")

        response = self.rechercher(self.eleve, "é")

        self.assertEqual(len(response.context["prospections"]), 1)
        self.assertContains(response, "Ecole Écho")
