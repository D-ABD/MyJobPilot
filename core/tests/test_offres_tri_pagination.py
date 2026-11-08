from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.views import _trier_offres


class TriEtPaginationOffresTests(TestCase):
    def setUp(self):
        self.url = reverse("core:offres_alternance")

    @patch("core.views.rechercher_entreprises_lba", return_value=[])
    @patch("core.views.rechercher_offres_lba")
    def test_tri_plus_recent_apres_dedoublonnage(self, mock_offres, mock_entreprises):
        offres = [
            {"titre": "Ancienne", "_publication_creation": "2026-01-01T00:00:00Z", "_rome_codes": ["M1805"]},
            {"titre": "Récente", "_publication_creation": "2026-10-01T00:00:00Z", "_rome_codes": ["M1805"]},
            {"titre": "Date inconnue", "_publication_creation": None, "_rome_codes": ["M1805"]},
        ]
        mock_offres.return_value = offres

        response = self.client.get(self.url, {"code_rome": "M1805", "ville": "75001", "rayon": 30})

        self.assertEqual([item["titre"] for item in response.context["offres"]], ["Récente", "Ancienne", "Date inconnue"])
        mock_entreprises.assert_called_once()

    def test_tri_pertinence_lba_conserve_ordre_api(self):
        offres = [{"titre": titre, "_rome_codes": ["M1805"]} for titre in ("LBA 1", "LBA 2", "LBA 3")]

        self.assertEqual(_trier_offres(offres, "lba", ["M1805"]), offres)

    def test_tri_ordre_saisi_codes_rome_ne_duplique_pas_une_offre_multi_codes(self):
        offres = [
            {"titre": "Deux codes", "_rome_codes": ["M1805", "I1401"]},
            {"titre": "M seulement", "_rome_codes": ["M1805"]},
            {"titre": "I seulement", "_rome_codes": ["I1401"]},
            {"titre": "Aucun code", "_rome_codes": []},
        ]

        resultat = _trier_offres(offres, "rome", ["I1401", "M1805"])

        self.assertEqual([offre["titre"] for offre in resultat], ["Deux codes", "I seulement", "M seulement", "Aucun code"])
        self.assertEqual(len({offre["titre"] for offre in resultat}), len(resultat))

    @patch("core.views.rechercher_entreprises_lba", return_value=[])
    @patch("core.views.rechercher_offres_lba")
    def test_offres_paginees_20_par_page(self, mock_offres, mock_entreprises):
        mock_offres.return_value = [{"titre": f"Offre {index}", "_rome_codes": ["M1805"]} for index in range(25)]

        response = self.client.get(self.url, {
            "code_rome": "M1805", "ville": "75001", "rayon": 20, "page_offres": 2,
        })

        self.assertEqual(len(response.context["offres"]), 5)
        self.assertEqual(response.context["offres_page"].number, 2)
        mock_entreprises.assert_called_once()

    @patch("core.views.rechercher_entreprises_lba")
    @patch("core.views.rechercher_offres_lba")
    def test_entreprises_paginees_independamment(self, mock_offres, mock_entreprises):
        mock_offres.return_value = [{"titre": f"Offre {index}", "_rome_codes": ["M1805"]} for index in range(25)]
        mock_entreprises.return_value = [{"nom": f"Entreprise {index}"} for index in range(25)]

        response = self.client.get(self.url, {
            "code_rome": "M1805", "ville": "75001", "rayon": 20,
            "page_offres": 1, "page_entreprises": 2,
        })

        self.assertEqual(len(response.context["offres"]), 20)
        self.assertEqual(response.context["offres_page"].number, 1)
        self.assertEqual(len(response.context["entreprises"]), 5)
        self.assertEqual(response.context["entreprises_page"].number, 2)

    @patch("core.views.rechercher_entreprises_lba", return_value=[])
    @patch("core.views.rechercher_offres_lba")
    def test_liens_pagination_conservent_criteres_et_tri(self, mock_offres, mock_entreprises):
        mock_offres.return_value = [{"titre": f"Offre {index}", "_rome_codes": ["M1805", "I1401"]} for index in range(45)]

        response = self.client.get(self.url, {
            "code_rome": "M1805,I1401", "ville": "75001", "rayon": 35,
            "tri": "rome", "page_offres": 2,
        })

        self.assertEqual(response.status_code, 200)
        hrefs = [link["url"] for link in response.context["offres_pagination"]["page_links"]]
        self.assertTrue(any("code_rome=M1805%2CI1401" in href for href in hrefs))
        self.assertTrue(any("ville=75001" in href and "rayon=35" in href and "tri=rome" in href for href in hrefs))
        self.assertContains(response, "Précédent")
        self.assertContains(response, "Suivant")
