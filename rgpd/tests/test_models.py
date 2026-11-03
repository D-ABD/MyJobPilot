from django.test import TestCase

from comptes.models import Utilisateur
from rgpd.models import DemandeRGPD


class DemandeRGPDTests(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(username="rgpd_user", password="p")

    def test_creation_avec_description(self):
        demande = DemandeRGPD.objects.create(utilisateur=self.user, type="acces", description="Données de profil")
        self.assertEqual(demande.description, "Données de profil")

    def test_creation_sans_description(self):
        demande = DemandeRGPD.objects.create(utilisateur=self.user, type="effacement")
        self.assertEqual(demande.description, "")
        self.assertEqual(demande.statut, "recue")
