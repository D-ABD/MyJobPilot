"""Tests du hub superviseur et administrateur."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Utilisateur


class HubTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="hub_superviseur",
            password="MotDePasse2026!",
            role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre,
            is_valide=True,
        )
        self.admin = Utilisateur.objects.create_user(
            username="hub_admin",
            password="MotDePasse2026!",
            role=Utilisateur.Role.ADMIN,
            is_valide=True,
            is_staff=True,
        )
        self.eleve = Utilisateur.objects.create_user(
            username="hub_eleve",
            password="MotDePasse2026!",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            is_valide=True,
        )

    def test_hub_superviseur_affiche_cartes_attendues(self):
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("entreprises:hub"))
        self.assertEqual(response.status_code, 200)
        for libelle, lien in (
            ("Mes prospections", "/prospections/?mine=1"),
            ("Prospections de mes élèves", "/prospections/?eleves=1"),
            ("Mes élèves", "/staff/"),
        ):
            self.assertContains(response, libelle)
            self.assertContains(response, lien)
        self.assertNotContains(response, "Mes documents")

    def test_hub_admin_affiche_cartes_attendues(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("entreprises:hub"))
        self.assertEqual(response.status_code, 200)
        for libelle, lien in (
            ("Mes prospections", "/prospections/?mine=1"),
            ("Toutes les prospections", "/prospections/"),
            ("Prospections des élèves", "/prospections/?eleves=1"),
            ("Prospections des superviseurs", "/prospections/?superviseurs=1"),
            ("Dashboard admin", "/admin-dashboard/"),
            ("Superviseurs", "/admin-dashboard/superviseurs/"),
            ("Import CSV élèves", "/admin-dashboard/import-eleves/"),
        ):
            self.assertContains(response, libelle)
            self.assertContains(response, lien)
        self.assertNotContains(response, "Mes documents")

    def test_hub_refuse_un_eleve(self):
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("entreprises:hub"))
        self.assertEqual(response.status_code, 403)

    def test_hub_redirige_un_visiteur_vers_connexion(self):
        response = self.client.get(reverse("entreprises:hub"))
        self.assertEqual(response.status_code, 302)
