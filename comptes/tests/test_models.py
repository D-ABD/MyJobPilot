"""Tests des contraintes et propriétés des modèles du Lot 1."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from comptes.models import (
    Centre,
    ConsentementRGPD,
    Formation,
    JournalAction,
    ScopeSuperviseur,
    Utilisateur,
)


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
        utilisateur = Utilisateur(
            username="eleve",
            password="mot-de-passe-valide",
            role=Utilisateur.Role.ELEVE,
            formation=self.formation,
        )
        with self.assertRaises(ValidationError) as erreur:
            utilisateur.full_clean()
        self.assertIn("centre", erreur.exception.message_dict)

    def test_clean_eleve_sans_formation_echoue(self):
        utilisateur = Utilisateur(
            username="eleve",
            password="mot-de-passe-valide",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
        )
        with self.assertRaises(ValidationError) as erreur:
            utilisateur.full_clean()
        self.assertIn("formation", erreur.exception.message_dict)

    def test_clean_superviseur_sans_centre_echoue(self):
        utilisateur = Utilisateur(
            username="superviseur",
            password="mot-de-passe-valide",
            role=Utilisateur.Role.SUPERVISEUR,
        )
        with self.assertRaises(ValidationError) as erreur:
            utilisateur.full_clean()
        self.assertIn("centre", erreur.exception.message_dict)

    def test_clean_admin_sans_centre_est_valide(self):
        utilisateur = Utilisateur(
            username="admin",
            password="mot-de-passe-valide",
            role=Utilisateur.Role.ADMIN,
        )
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

    def creer_superviseur(self):
        return Utilisateur.objects.create_user(
            username="scope_superviseur",
            password=None,
            role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre,
            is_staff=True,
            is_valide=True,
        )

    def test_scope_str_contient_superviseur_et_centre(self):
        superviseur = self.creer_superviseur()
        scope = ScopeSuperviseur.objects.create(superviseur=superviseur, centre=self.centre)
        self.assertIn(superviseur.username, str(scope))
        self.assertIn(self.centre.nom, str(scope))

    def test_scope_superviseur_centre_est_unique(self):
        superviseur = self.creer_superviseur()
        ScopeSuperviseur.objects.create(superviseur=superviseur, centre=self.centre)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ScopeSuperviseur.objects.create(superviseur=superviseur, centre=self.centre)

    def test_desactiver_scope_renseigne_date_et_journalise(self):
        superviseur = self.creer_superviseur()
        scope = ScopeSuperviseur.objects.create(superviseur=superviseur, centre=self.centre)
        scope.desactiver(auteur=superviseur)
        scope.refresh_from_db()
        self.assertFalse(scope.is_active)
        self.assertIsNotNone(scope.date_desactivation)
        action = JournalAction.objects.get(action=JournalAction.Action.ACCES_SCOPE_REFUSE)
        self.assertEqual(action.cible_type, "ScopeSuperviseur")
        self.assertEqual(action.cible_id, str(scope.pk))
        self.assertEqual(action.details["action"], "desactivation")

    def test_desactiver_scope_deux_fois_est_idempotent(self):
        superviseur = self.creer_superviseur()
        scope = ScopeSuperviseur.objects.create(superviseur=superviseur, centre=self.centre)
        scope.desactiver(auteur=superviseur)
        scope.refresh_from_db()
        premiere_date = scope.date_desactivation
        scope.desactiver(auteur=superviseur)
        scope.refresh_from_db()
        self.assertEqual(scope.date_desactivation, premiere_date)
        self.assertEqual(JournalAction.objects.filter(action=JournalAction.Action.ACCES_SCOPE_REFUSE).count(), 1)

    def test_creer_scope_journalise_une_seule_fois(self):
        superviseur = self.creer_superviseur()
        scope, cree = ScopeSuperviseur.creer(superviseur, self.centre, auteur=superviseur)
        meme_scope, cree_une_seconde_fois = ScopeSuperviseur.creer(
            superviseur,
            self.centre,
            auteur=superviseur,
        )
        self.assertTrue(cree)
        self.assertFalse(cree_une_seconde_fois)
        self.assertEqual(scope, meme_scope)
        journal = JournalAction.objects.get(action=JournalAction.Action.SCOPE_CREE)
        self.assertEqual(journal.cible_id, str(scope.pk))
        self.assertEqual(journal.details["superviseur_id"], superviseur.pk)
        self.assertEqual(journal.details["centre_id"], self.centre.pk)
