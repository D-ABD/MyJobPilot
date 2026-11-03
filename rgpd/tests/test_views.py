from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Centre, Formation, Utilisateur
from rgpd.models import DemandeRGPD


class DemandesRGPDViewsTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(nom="Centre Paris", defaults={"departement": "75 - Paris"})
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS Test")
        self.user = Utilisateur.objects.create_user(
            username="rgpd_eleve", password="MotDePasse2026!", role="eleve",
            centre=self.centre, formation=self.formation, is_valide=True,
        )
        self.admin = Utilisateur.objects.create_user(username="rgpd_admin", password="p", role="admin", is_staff=True)

    def test_eleve_cree_demande_avec_description(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("rgpd:demande_rgpd_create"), {"type": "acces", "description": "Mon profil"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DemandeRGPD.objects.get().description, "Mon profil")

    def test_eleve_cree_demande_sans_description(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("rgpd:demande_rgpd_create"), {"type": "rectification"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DemandeRGPD.objects.get().description, "")

    def test_eleve_ne_voit_pas_demande_autre_utilisateur(self):
        other = Utilisateur.objects.create_user(username="autre", password="p")
        demande = DemandeRGPD.objects.create(utilisateur=other, type="acces")
        self.client.force_login(self.user)
        response = self.client.get(reverse("rgpd:demande_rgpd_detail", args=[demande.pk]))
        self.assertEqual(response.status_code, 404)

    def test_admin_traite_demande_date_aware(self):
        demande = DemandeRGPD.objects.create(utilisateur=self.user, type="opposition")
        self.client.force_login(self.admin)
        response = self.client.post(reverse("rgpd:admin_demande_rgpd_traiter", args=[demande.pk]), {
            "statut": "traitee", "motif_refus": "",
        })
        self.assertEqual(response.status_code, 302)
        demande.refresh_from_db()
        self.assertEqual(demande.traitee_par, self.admin)
        self.assertTrue(timezone.is_aware(demande.date_traitement))
