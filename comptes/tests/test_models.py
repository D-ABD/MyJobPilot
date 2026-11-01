"""Tests des contraintes et propriétés des modèles du Lot 1."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from comptes.models import Centre, ConsentementRGPD, Formation, Utilisateur


class ModelesComptesTests(TestCase):
    def setUp(self):
        self.centre = Centre.objects.create(nom="Centre test", departement="75 - Paris")
        self.formation = Formation.objects.create(centre=self.centre, nom="BTS Test")

    def test_str_centre_contient_nom_et_departement(self):
        self.assertIn("Centre test", str(self.centre))
        self.assertIn("75 - Paris", str(self.centre))

    def test_formation_est_unique_par_centre(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Formation.objects.create(centre=self.centre, nom="BTS Test")

    def test_departement_utilisateur_vient_du_centre(self):
        utilisateur = Utilisateur(
            username="eleve",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
        )
        self.assertEqual(utilisateur.departement, "75 - Paris")

    def test_departement_utilisateur_sans_centre_est_none(self):
        utilisateur = Utilisateur(username="admin", role=Utilisateur.Role.ADMIN)
        self.assertIsNone(utilisateur.departement)

    def test_clean_eleve_sans_centre_echoue(self):
        utilisateur = Utilisateur(username="eleve", role=Utilisateur.Role.ELEVE, formation=self.formation)
        with self.assertRaises(ValidationError):
            utilisateur.full_clean()

    def test_clean_eleve_sans_formation_echoue(self):
        utilisateur = Utilisateur(username="eleve", role=Utilisateur.Role.ELEVE, centre=self.centre)
        with self.assertRaises(ValidationError):
            utilisateur.full_clean()

    def test_clean_superviseur_sans_centre_echoue(self):
        utilisateur = Utilisateur(username="superviseur", role=Utilisateur.Role.SUPERVISEUR)
        with self.assertRaises(ValidationError):
            utilisateur.full_clean()

    def test_clean_admin_sans_centre_est_valide(self):
        utilisateur = Utilisateur(username="admin", role=Utilisateur.Role.ADMIN)
        utilisateur.full_clean()

    def test_role_par_defaut_est_eleve(self):
        self.assertEqual(Utilisateur().role, Utilisateur.Role.ELEVE)

    def test_superutilisateur_devient_admin_valide(self):
        administrateur = Utilisateur.objects.create_superuser(
            username="admin_auto",
            email="admin@example.com",
            password="MotDePasse2026!",
        )
        self.assertEqual(administrateur.role, Utilisateur.Role.ADMIN)
        self.assertTrue(administrateur.is_valide)

    def test_a_consenti_rgpd_false_si_pas_de_consentement(self):
        utilisateur = Utilisateur.objects.create_user(username="no_consent", password="p")
        self.assertFalse(utilisateur.a_consenti_rgpd)

    def test_a_consenti_rgpd_true_si_consentement_existe(self):
        utilisateur = Utilisateur.objects.create_user(username="with_consent", password="p")
        ConsentementRGPD.objects.create(utilisateur=utilisateur, version_politique="1.0")
        self.assertTrue(utilisateur.a_consenti_rgpd)
