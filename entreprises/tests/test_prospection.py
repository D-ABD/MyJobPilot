"""Tests du formulaire et du rattachement d'une prospection."""
from django.test import TestCase

from comptes.models import Centre, Formation, Utilisateur
from entreprises.forms import ProspectionForm
from entreprises.models import Entreprise, Prospection, Statut


class ProspectionTests(TestCase):
    def setUp(self):
        centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        formation, _ = Formation.objects.get_or_create(centre=centre, nom="BTS SIO")
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_prospection",
            password="mot-de-passe",
            role=Utilisateur.Role.ELEVE,
            centre=centre,
            formation=formation,
        )
        self.entreprise = Entreprise.objects.create(nom="Entreprise Prospection")

    def test_formulaire_accepte_une_entreprise_existante(self):
        form = ProspectionForm(
            {
                "entreprise_id": self.entreprise.pk,
                "entreprise_nom": self.entreprise.nom,
                "statut": Statut.A_CONTACTER,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["entreprise_id"], self.entreprise)

    def test_formulaire_refuse_une_prospection_sans_entreprise(self):
        form = ProspectionForm({"statut": Statut.A_CONTACTER})
        self.assertFalse(form.is_valid())
        self.assertIn("entreprise_nom", form.errors)

    def test_formulaire_exige_une_date_de_relance_pour_le_statut_correspondant(self):
        form = ProspectionForm(
            {
                "entreprise_id": self.entreprise.pk,
                "statut": Statut.A_RELANCER,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("date_relance", form.errors)

    def test_prospection_est_rattachee_a_un_eleve_et_a_une_entreprise(self):
        prospection = Prospection.objects.create(eleve=self.eleve, entreprise=self.entreprise)
        self.assertEqual(self.eleve.prospections.get(), prospection)
        self.assertEqual(self.entreprise.prospections.get(), prospection)
