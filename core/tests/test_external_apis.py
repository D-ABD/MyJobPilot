from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import requests
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, Utilisateur
from core.external_apis import CACHE_TIMEOUT, rechercher_entreprises_lba, rechercher_offres_lba


class ExternalApisTests(TestCase):
    def setUp(self):
        self.lba_key_patch = patch.dict("os.environ", {"LBA_API_KEY": ""})
        self.lba_key_patch.start()
        self.addCleanup(self.lba_key_patch.stop)
        cache.clear()
        self.centre = Centre.objects.create(nom="Centre offres", departement="75 - Paris")
        self.formation = Formation.objects.create(centre=self.centre, nom="Formation offres")

    def creer_eleve(self):
        return Utilisateur.objects.create_user(
            username="eleve_offres",
            password="test",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def response(self, data=None, status=200):
        response = Mock()
        response.status_code = status
        response.raise_for_status.side_effect = requests.HTTPError("API error") if status >= 400 else None
        response.json.return_value = data
        return response

    def geo_response(self):
        return self.response([{
            "nom": "Paris",
            "localisation": {"centre": {"type": "Point", "coordinates": [2.3522, 48.8566]}},
        }])

    def opportunities_response(self):
        return self.response({
            "jobs": [{
                "identifier": {"id": "offre-1"},
                "offer": {
                    "title": "Développeur web",
                    "rome_codes": ["M1805"],
                    "publication": {"creation": "2026-11-01T10:00:00Z"},
                },
                "workplace": {"name": "Atelier Numérique"},
                "location": {"address": "10 rue Exemple, 75001 Paris"},
                "apply": {"url": "https://example.org/candidater"},
            }, {
                "identifier": {"id": "offre-1"},
                "offer": {"title": "Doublon LBA", "rome_codes": ["I1401"]},
                "workplace": {"name": "Autre nom"},
            }],
            "recruiters": [{
                "identifier": {"id": "recruteur-1"},
                "workplace": {"name": "Entreprise Alpha"},
                "location": {"address": "5 avenue Exemple, 75002 Paris"},
                "domain": {"label": "Informatique"},
            }],
        })

    @patch("core.external_apis.requests.get")
    def test_rechercher_offres_lba_retourne_liste(self, mock_get):
        mock_get.side_effect = [self.geo_response(), self.opportunities_response()]

        resultat = rechercher_offres_lba("M1805", "75001", 20)

        self.assertEqual(resultat, [{
            "_id": "offre-1",
            "_rome_codes": ["M1805"],
            "_publication_creation": "2026-11-01T10:00:00Z",
            "titre": "Développeur web",
            "entreprise": "Atelier Numérique",
            "ville": "Paris",
            "url": "https://example.org/candidater",
        }])
        self.assertEqual(mock_get.call_args_list[1].args[0], "https://api.apprentissage.beta.gouv.fr/api/job/v1/search")
        self.assertEqual(mock_get.call_args_list[1].kwargs["params"]["romes"], "M1805")
        self.assertNotIn("Authorization", mock_get.call_args_list[0].kwargs["headers"])

    @patch("core.external_apis.requests.get")
    def test_rechercher_offres_lba_gere_erreur_api(self, mock_get):
        mock_get.side_effect = [self.geo_response(), self.response(status=500)]

        self.assertEqual(rechercher_offres_lba("M1805", "75001", 20), [])

    @patch("core.external_apis.requests.get")
    def test_rechercher_entreprises_lba_retourne_liste(self, mock_get):
        mock_get.side_effect = [self.geo_response(), self.opportunities_response()]

        resultat = rechercher_entreprises_lba("M1805", "75001", 20)

        self.assertEqual(resultat, [{
            "_id": "recruteur-1",
            "nom": "Entreprise Alpha",
            "secteur": "Informatique",
            "ville": "Paris",
        }])

    @patch("core.external_apis.requests.get")
    def test_rechercher_entreprises_lba_gere_erreur_api(self, mock_get):
        mock_get.side_effect = [self.geo_response(), self.response(status=500)]

        self.assertEqual(rechercher_entreprises_lba("M1805", "75001", 20), [])

    @patch("core.external_apis.requests.get")
    def test_cache_actif_1h(self, mock_get):
        mock_get.side_effect = [self.geo_response(), self.opportunities_response()]

        premier = rechercher_offres_lba("M1805", "75001", 20)
        appels_apres_premiere_recherche = mock_get.call_count
        second = rechercher_offres_lba("M1805", "75001", 20)

        self.assertEqual(premier, second)
        self.assertEqual(appels_apres_premiere_recherche, 2)  # géolocalisation LBA + recherche LBA
        self.assertEqual(mock_get.call_count, appels_apres_premiere_recherche)
        self.assertEqual(CACHE_TIMEOUT, 60 * 60)

    def test_page_offres_accessible_sans_auth(self):
        response = self.client.get(reverse("core:offres_alternance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trouver une alternance")

    def test_page_offres_accessible_avec_auth(self):
        self.client.force_login(self.creer_eleve())

        response = self.client.get(reverse("core:offres_alternance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trouver une alternance")

    def test_bouton_creer_prospection_prefill(self):
        eleve = self.creer_eleve()
        superviseur = Utilisateur.objects.create_user(
            username="superviseur_offres", password="test", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre, is_valide=True,
        )
        admin = Utilisateur.objects.create_superuser(
            username="admin_offres", email="admin-offres@example.com", password="test",
        )
        destinations = (
            (eleve, "/entreprises/nouvelle/"),
            (superviseur, "/prospections/nouvelle/"),
            (admin, "/prospections/nouvelle/"),
        )
        for utilisateur, chemin in destinations:
            with self.subTest(role=utilisateur.role):
                self.client.force_login(utilisateur)
                response = self.client.post(reverse("core:offres_alternance"), {
                    "creer_prospection": "1",
                    "entreprise_nom": "Entreprise Alpha",
                    "ville": "Paris",
                    "secteur": "Informatique",
                })
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlparse(response.url).path, chemin)
                params = parse_qs(urlparse(response.url).query)
                self.assertEqual(params["entreprise_nom"], ["Entreprise Alpha"])
                self.assertEqual(params["ville"], ["Paris"])
                self.assertEqual(params["secteur"], ["Informatique"])
