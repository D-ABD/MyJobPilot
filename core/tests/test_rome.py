from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, Utilisateur
from core.forms import OffresAlternanceForm


class RechercheRomeTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre ROME",
            defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(
            centre=self.centre,
            nom="Formation ROME",
        )

    def creer_utilisateur(self, username, role, codes_rome=""):
        return Utilisateur.objects.create_user(
            username=username,
            password="test",
            role=role,
            centre=self.centre if role != Utilisateur.Role.ADMIN else None,
            formation=self.formation if role == Utilisateur.Role.ELEVE else None,
            codes_rome=codes_rome,
            is_valide=True,
        )

    def _formulaire_codes(self, code_rome):
        return OffresAlternanceForm(data={
            "code_rome": code_rome,
            "ville": "75001",
            "rayon": "30",
            "tri": "recent",
        })

    def test_code_rome_avec_espace_insecable_est_accepte(self):
        form = self._formulaire_codes("K1801\xa0")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["code_rome"], "K1801")

    def test_code_rome_avec_bom_est_accepte(self):
        form = self._formulaire_codes("\ufeffK1801")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["code_rome"], "K1801")

    def test_code_rome_avec_espaces_multiples_est_normalise(self):
        form = self._formulaire_codes("K1801 , I1401")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["code_rome"], "K1801,I1401")

    def test_code_rome_avec_caractere_controle_reste_invalide(self):
        form = self._formulaire_codes("K1801\x00")

        self.assertFalse(form.is_valid())
        self.assertIn("code_rome", form.errors)

    @patch("core.views.rechercher_entreprises_lba", return_value=[])
    @patch("core.views.rechercher_offres_lba", return_value=[])
    def test_code_rome_valide_est_transmis_a_api(self, mock_offres, mock_entreprises):
        response = self.client.get(reverse("core:offres_alternance"), {
            "code_rome": "M1805,I1401",
            "ville": "75001",
            "rayon": "30",
            "tri": "recent",
        })

        self.assertEqual(response.status_code, 200)
        mock_offres.assert_called_once_with("M1805,I1401", "75001", 30)
        mock_entreprises.assert_called_once_with("M1805,I1401", "75001", 30)

    @patch("core.views.rechercher_entreprises_lba")
    @patch("core.views.rechercher_offres_lba")
    def test_code_rome_format_invalide_affiche_erreur_et_rejette_plus_de_trois(self, mock_offres, mock_entreprises):
        for codes, message in (
            ("M18X5", "codes ROME valides"),
            ("M1805,I1401,D1406,F1601", "Maximum 3 codes ROME par recherche."),
        ):
            with self.subTest(codes=codes):
                response = self.client.get(reverse("core:offres_alternance"), {
                    "code_rome": codes,
                    "ville": "75001",
                    "rayon": "30",
                })
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
        mock_offres.assert_not_called()
        mock_entreprises.assert_not_called()

    def _verifier_pre_remplissage(self, role, username):
        utilisateur = self.creer_utilisateur(username, role, "M1805,I1401")
        self.client.force_login(utilisateur)
        response = self.client.get(reverse("core:offres_alternance"))
        self.assertEqual(response.context["form"]["code_rome"].value(), "M1805,I1401")

    def test_champ_pre_rempli_pour_eleve_avec_codes_rome(self):
        self._verifier_pre_remplissage(Utilisateur.Role.ELEVE, "eleve_rome")

    def test_champ_pre_rempli_pour_superviseur_avec_codes_rome(self):
        self._verifier_pre_remplissage(Utilisateur.Role.SUPERVISEUR, "superviseur_rome")

    def test_champ_pre_rempli_pour_admin_avec_codes_rome(self):
        self._verifier_pre_remplissage(Utilisateur.Role.ADMIN, "admin_rome")

    @patch("core.views.rechercher_entreprises_lba")
    @patch("core.views.rechercher_offres_lba")
    def test_utilisateur_sans_code_rome_voit_message_aide(self, mock_offres, mock_entreprises):
        response = self.client.get(reverse("core:offres_alternance"), {
            "code_rome": "",
            "ville": "75001",
            "rayon": "20",
        })

        self.assertContains(response, "Saisissez votre code ROME, ou consultez le référentiel France Travail.")
        mock_offres.assert_not_called()
        mock_entreprises.assert_not_called()

    def test_lien_referentiel_rome_present_dans_template(self):
        response = self.client.get(reverse("core:offres_alternance"))

        self.assertContains(response, 'href="https://candidat.francetravail.fr/metierscope/"')
