"""Tests des fonctions de session, d'adresse IP et de journalisation."""
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from comptes.models import JournalAction, Utilisateur
from comptes.utils import get_client_ip, invalidate_user_sessions, log_action


class UtilitairesComptesTests(TestCase):
    def creer_session(self, utilisateur):
        session = SessionStore()
        session["_auth_user_id"] = str(utilisateur.pk)
        session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session.save()
        return session.session_key

    def test_invalidation_ne_supprime_que_les_sessions_du_compte(self):
        utilisateur_1 = Utilisateur.objects.create_user(username="user1", password="p")
        utilisateur_2 = Utilisateur.objects.create_user(username="user2", password="p")
        cle_1 = self.creer_session(utilisateur_1)
        cle_2 = self.creer_session(utilisateur_2)

        self.assertEqual(invalidate_user_sessions(utilisateur_1), 1)
        self.assertFalse(SessionStore(session_key=cle_1).exists(cle_1))
        self.assertTrue(SessionStore(session_key=cle_2).exists(cle_2))

    def test_invalidation_none_retourne_zero(self):
        self.assertEqual(invalidate_user_sessions(None), 0)

    def test_invalidation_sans_session_retourne_zero(self):
        utilisateur = Utilisateur.objects.create_user(username="sans_session", password="p")
        self.assertEqual(invalidate_user_sessions(utilisateur), 0)

    def test_get_client_ip_priorise_x_forwarded_for(self):
        requete = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.1", REMOTE_ADDR="192.0.2.5")
        self.assertEqual(get_client_ip(requete), "203.0.113.10")

    def test_get_client_ip_utilise_remote_addr_en_repli(self):
        requete = RequestFactory().get("/", REMOTE_ADDR="192.0.2.5")
        self.assertEqual(get_client_ip(requete), "192.0.2.5")

    def test_log_action_enregistre_les_champs(self):
        utilisateur = Utilisateur.objects.create_user(username="journal", password="p")
        requete = RequestFactory().post("/", REMOTE_ADDR="192.0.2.7", HTTP_USER_AGENT="Test navigateur")
        entree = log_action(
            JournalAction.Action.COMPTE_VALIDE,
            utilisateur=utilisateur,
            cible=utilisateur,
            details={"source": "test"},
            request=requete,
        )
        self.assertEqual(entree.utilisateur, utilisateur)
        self.assertEqual(entree.cible_type, "comptes.Utilisateur")
        self.assertEqual(entree.cible_id, str(utilisateur.pk))
        self.assertEqual(entree.ip, "192.0.2.7")
        self.assertEqual(entree.user_agent, "Test navigateur")
        self.assertEqual(entree.details, {"source": "test"})
