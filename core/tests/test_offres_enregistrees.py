from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch

from comptes.models import Utilisateur
from core.models import OffreEnregistree


class OffresEnregistreesTests(TestCase):
    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="favori_user", password="test", role=Utilisateur.Role.ADMIN,
        )
        self.autre_utilisateur = Utilisateur.objects.create_user(
            username="autre_favori_user", password="test", role=Utilisateur.Role.ADMIN,
        )
        self.client.force_login(self.utilisateur)
        self.client_csrf = Client(enforce_csrf_checks=True)
        self.client_csrf.force_login(self.utilisateur)

    def _offre(self, offre_id_lba, utilisateur=None, titre=None):
        return OffreEnregistree.objects.create(
            utilisateur=utilisateur or self.utilisateur,
            offre_id_lba=offre_id_lba,
            titre=titre or f"Offre {offre_id_lba}",
            entreprise="Entreprise test",
            ville="Paris",
            url="https://example.test/offre",
            date_publication="2026-03-01T12:00:00Z",
        )

    def _csrf_token(self):
        self.client_csrf.get(reverse("core:offres_alternance"))
        return self.client_csrf.cookies["csrftoken"].value

    def _donnees_offre(self):
        return {
            "titre": "Développeur web",
            "entreprise": "Acme",
            "ville": "Paris",
            "url": "https://example.test/jobs/1",
            "date_publication": "2026-03-01T12:00:00Z",
        }

    def test_enregistrer_offre_connecte_cree_favori(self):
        url = reverse("core:enregistrer_offre", args=["lba-1"])
        token = self._csrf_token()

        refus_csrf = self.client_csrf.post(url, self._donnees_offre())
        self.assertEqual(refus_csrf.status_code, 403)
        self.assertFalse(OffreEnregistree.objects.exists())

        response = self.client_csrf.post(url, {**self._donnees_offre(), "csrfmiddlewaretoken": token})

        self.assertRedirects(response, reverse("core:mes_offres_enregistrees"))
        favori = OffreEnregistree.objects.get(utilisateur=self.utilisateur, offre_id_lba="lba-1")
        self.assertEqual(favori.titre, "Développeur web")
        self.assertEqual(favori.date_publication.isoformat(), "2026-03-01T12:00:00+00:00")

    def test_enregistrer_offre_non_connecte_redirige_login(self):
        response = Client().post(
            reverse("core:enregistrer_offre", args=["lba-1"]), self._donnees_offre(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    def test_enregistrer_offre_deja_enregistree_ne_cree_pas_doublon(self):
        url = reverse("core:enregistrer_offre", args=["lba-1"])
        token = self._csrf_token()
        data = {**self._donnees_offre(), "csrfmiddlewaretoken": token}

        self.client_csrf.post(url, data)
        self.client_csrf.post(url, data)

        self.assertEqual(OffreEnregistree.objects.filter(
            utilisateur=self.utilisateur, offre_id_lba="lba-1",
        ).count(), 1)

    def test_retirer_offre_supprime_favori(self):
        self._offre("lba-1")
        url = reverse("core:retirer_offre", args=["lba-1"])
        token = self._csrf_token()

        refus_csrf = self.client_csrf.post(url)
        self.assertEqual(refus_csrf.status_code, 403)
        self.assertTrue(OffreEnregistree.objects.filter(utilisateur=self.utilisateur).exists())

        response = self.client_csrf.post(url, {"csrfmiddlewaretoken": token})

        self.assertRedirects(response, reverse("core:mes_offres_enregistrees"))
        self.assertFalse(OffreEnregistree.objects.filter(utilisateur=self.utilisateur).exists())

    def test_retirer_offre_non_connecte_redirige_login(self):
        response = Client().post(reverse("core:retirer_offre", args=["lba-1"]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    def test_utilisateur_ne_peut_pas_retirer_favori_autre_utilisateur(self):
        favori = self._offre("lba-prive", utilisateur=self.autre_utilisateur)

        self.client.post(reverse("core:retirer_offre", args=[favori.offre_id_lba]))

        self.assertTrue(OffreEnregistree.objects.filter(pk=favori.pk).exists())

    def test_mes_offres_enregistrees_liste_uniquement_les_favoris_de_l_utilisateur(self):
        self._offre("lba-mien")
        self._offre("lba-autre", utilisateur=self.autre_utilisateur)

        response = self.client.get(reverse("core:mes_offres_enregistrees"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Offre lba-mien")
        self.assertNotContains(response, "Offre lba-autre")

    def test_mes_offres_enregistrees_pagine_20_par_page(self):
        OffreEnregistree.objects.bulk_create([
            OffreEnregistree(
                utilisateur=self.utilisateur,
                offre_id_lba=f"lba-{numero}",
                titre=f"Offre {numero}",
            )
            for numero in range(23)
        ])

        response = self.client.get(reverse("core:mes_offres_enregistrees"), {"page": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["offres"]), 3)
        self.assertEqual(response.context["offres_page"].number, 2)
        self.assertContains(response, "Précédent")

    def test_mes_offres_enregistrees_non_connecte_redirige_login(self):
        response = Client().get(reverse("core:mes_offres_enregistrees"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    @patch("core.views.rechercher_entreprises_lba", return_value=[])
    @patch("core.views.rechercher_offres_lba")
    def test_bouton_enregistrer_visible_sur_offres_non_enregistrees(self, mock_offres, _mock_entreprises):
        mock_offres.return_value = [{
            "_id": "lba-neuf",
            "_publication_creation": "2026-03-01T12:00:00Z",
            "titre": "Développeur web",
            "entreprise": "Acme",
            "ville": "Paris",
            "url": "https://example.test/jobs/1",
        }]

        response = self.client.get(reverse("core:offres_alternance"), {
            "code_rome": "M1805", "ville": "75001", "rayon": "20",
        })

        self.assertContains(response, "Enregistrer")
        self.assertContains(response, reverse("core:enregistrer_offre", args=["lba-neuf"]))
        self.assertContains(response, 'name="date_publication" value="2026-03-01T12:00:00Z"')
        self.assertContains(response, 'target="_blank"')

    @patch("core.views.rechercher_entreprises_lba", return_value=[])
    @patch("core.views.rechercher_offres_lba")
    def test_bouton_deja_enregistree_visible_sur_offres_enregistrees(self, mock_offres, _mock_entreprises):
        self._offre("lba-deja")
        mock_offres.return_value = [{
            "_id": "lba-deja",
            "_publication_creation": None,
            "titre": "Déjà sauvegardée",
            "entreprise": "Acme",
            "ville": "Paris",
            "url": "https://example.test/jobs/1",
        }]

        response = self.client.get(reverse("core:offres_alternance"), {
            "code_rome": "M1805", "ville": "75001", "rayon": "20",
        })

        self.assertContains(response, "Déjà enregistrée")
        self.assertContains(response, reverse("core:retirer_offre", args=["lba-deja"]))

    def test_lien_mes_offres_enregistrees_visible_dans_nav_si_authentifie(self):
        response = self.client.get(reverse("core:offres_alternance"))

        self.assertContains(response, reverse("core:mes_offres_enregistrees"))
        self.assertContains(response, "Mes offres enregistrées")

    def test_lien_mes_offres_enregistrees_absent_si_non_authentifie(self):
        response = Client().get(reverse("core:offres_alternance"))

        self.assertNotContains(response, "Mes offres enregistrées")
