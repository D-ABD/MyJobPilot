"""Tests du workflow public et de l'authentification du Lot 1."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, ConsentementRGPD, Formation, JournalAction, Utilisateur


class VuesComptesTests(TestCase):
    def setUp(self):
        self.centre = Centre.objects.create(nom="Centre test", departement="75 - Paris")
        self.formation = Formation.objects.create(centre=self.centre, nom="BTS Test")
        self.autre_centre = Centre.objects.create(nom="Centre autre", departement="69 - Rhône")
        self.autre_formation = Formation.objects.create(centre=self.autre_centre, nom="BUT Test")
        self.donnees_inscription = {
            "username": "nouveau",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "j@example.com",
            "centre": self.centre.pk,
            "formation": self.formation.pk,
            "password1": "MotDePasse2026!",
            "password2": "MotDePasse2026!",
            "consentement_rgpd": True,
        }

    def test_get_inscription_affiche_le_formulaire(self):
        response = self.client.get(reverse("comptes:inscription"))
        self.assertEqual(response.status_code, 200)

    def test_post_cree_eleve_non_valide(self):
        response = self.client.post(reverse("comptes:inscription"), self.donnees_inscription)
        self.assertEqual(response.status_code, 302)
        utilisateur = Utilisateur.objects.get(username="nouveau")
        self.assertEqual(utilisateur.role, Utilisateur.Role.ELEVE)
        self.assertFalse(utilisateur.is_valide)
        self.assertTrue(
            JournalAction.objects.filter(
                action=JournalAction.Action.INSCRIPTION_SOUMISE,
                utilisateur=utilisateur,
            ).exists()
        )
        self.assertTrue(ConsentementRGPD.objects.filter(utilisateur=utilisateur).exists())

    def test_post_formation_hors_centre_est_rejete(self):
        donnees = {**self.donnees_inscription, "formation": self.autre_formation.pk}
        response = self.client.post(reverse("comptes:inscription"), donnees)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(username="nouveau").exists())

    def test_post_sans_consentement_rejete(self):
        donnees = {**self.donnees_inscription, "username": "sans_consent", "consentement_rgpd": ""}
        response = self.client.post(reverse("comptes:inscription"), donnees)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(username="sans_consent").exists())

    def test_eleve_non_valide_sur_accueil_est_redirige(self):
        utilisateur = Utilisateur.objects.create_user(
            username="attente",
            password="p",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=False,
        )
        self.client.force_login(utilisateur)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("comptes:en_attente"))

    def test_eleve_non_valide_accede_a_la_page_attente(self):
        utilisateur = Utilisateur.objects.create_user(
            username="attente",
            password="p",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=False,
        )
        self.client.force_login(utilisateur)
        response = self.client.get(reverse("comptes:en_attente"))
        self.assertEqual(response.status_code, 200)

    def test_eleve_non_valide_peut_se_deconnecter(self):
        utilisateur = Utilisateur.objects.create_user(
            username="attente",
            password="p",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=False,
        )
        self.client.force_login(utilisateur)
        response = self.client.post(reverse("comptes:deconnexion"))
        self.assertRedirects(response, reverse("comptes:connexion"))

    def test_eleve_valide_accede_a_l_accueil(self):
        utilisateur = Utilisateur.objects.create_user(
            username="valide",
            password="p",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )
        self.client.force_login(utilisateur)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_redirection_apres_login_eleve_non_valide(self):
        utilisateur = Utilisateur.objects.create_user(
            username="attente",
            password="p",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=False,
        )
        self.client.force_login(utilisateur)
        response = self.client.get(reverse("comptes:redirection_apres_login"))
        self.assertRedirects(response, reverse("comptes:en_attente"))

    def test_redirection_apres_login_admin_vers_admin_django(self):
        administrateur = Utilisateur.objects.create_superuser(
            username="administrateur",
            email="admin@example.com",
            password="p",
            role=Utilisateur.Role.ADMIN,
            is_valide=True,
        )
        self.client.force_login(administrateur)
        response = self.client.get(reverse("comptes:redirection_apres_login"))
        self.assertRedirects(response, "/admin/")

    def test_connexion_reussie_cree_action_login(self):
        utilisateur = Utilisateur.objects.create_user(username="login", password="MotDePasse2026!")
        response = self.client.post(
            reverse("comptes:connexion"),
            {"username": utilisateur.username, "password": "MotDePasse2026!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            JournalAction.objects.filter(action=JournalAction.Action.LOGIN, utilisateur=utilisateur).exists()
        )

    def test_mauvais_mot_de_passe_cree_action_login_failed(self):
        response = self.client.post(
            reverse("comptes:connexion"),
            {"username": "introuvable", "password": "mauvais"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(JournalAction.objects.filter(action=JournalAction.Action.LOGIN_FAILED).exists())
