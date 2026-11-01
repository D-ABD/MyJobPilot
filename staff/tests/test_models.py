"""Vérifie les chemins de création et de journalisation d'un scope."""
from django.test import TestCase

from comptes.models import Centre, JournalAction, ScopeSuperviseur, Utilisateur


class CreationScopeTests(TestCase):
    def setUp(self):
        self.centre = Centre.objects.create(nom="Centre staff modèle", departement="75 - Paris")
        self.superviseur = Utilisateur.objects.create_user(
            username="superviseur_modele",
            password=None,
            role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre,
            is_staff=True,
            is_valide=True,
        )

    def test_creation_via_creer_journalise_scope_cree(self):
        scope, created = ScopeSuperviseur.creer(
            superviseur=self.superviseur,
            centre=self.centre,
            auteur=self.superviseur,
        )
        self.assertTrue(created)
        self.assertTrue(scope.is_active)
        self.assertTrue(
            JournalAction.objects.filter(
                action=JournalAction.Action.SCOPE_CREE,
                cible_id=str(scope.pk),
            ).exists()
        )

    def test_creation_directe_ne_journalise_pas(self):
        scope = ScopeSuperviseur.objects.create(
            superviseur=self.superviseur,
            centre=self.centre,
        )
        self.assertFalse(
            JournalAction.objects.filter(
                cible_type="ScopeSuperviseur",
                cible_id=str(scope.pk),
            ).exists()
        )
