"""Tests des signaux d'authentification."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import JournalAction, Utilisateur


class SignauxComptesTests(TestCase):
    def test_post_deconnexion_cree_action_logout(self):
        utilisateur = Utilisateur.objects.create_user(username="logout", password="p")
        self.client.force_login(utilisateur)
        response = self.client.post(reverse("comptes:deconnexion"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            JournalAction.objects.filter(
                action=JournalAction.Action.LOGOUT,
                utilisateur=utilisateur,
            ).exists()
        )
