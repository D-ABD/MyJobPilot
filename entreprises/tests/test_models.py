"""Tests des modèles Entreprise et HistoriqueStatut."""
from django.test import TestCase

from comptes.models import Centre, Formation, Utilisateur
from entreprises.models import Entreprise, HistoriqueStatut, Statut


class ModelesEntreprisesTests(TestCase):
    def setUp(self):
        self.centre = Centre.objects.create(nom="Centre Paris", departement="75 - Paris")
        self.formation = Formation.objects.create(centre=self.centre, nom="BTS SIO")
        self.eleve = Utilisateur.objects.create_user(
            username="eleve",
            password="mot-de-passe-test",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def test_statut_par_defaut_est_a_contacter(self):
        entreprise = Entreprise.objects.create(eleve=self.eleve, nom="ACME")
        self.assertEqual(entreprise.statut, Statut.A_CONTACTER)

    def test_str_entreprise_contient_nom_et_statut(self):
        entreprise = Entreprise.objects.create(eleve=self.eleve, nom="ACME")
        self.assertIn("ACME", str(entreprise))
        self.assertIn(entreprise.get_statut_display(), str(entreprise))

    def test_creation_entreprise_avec_champs_obligatoires(self):
        entreprise = Entreprise.objects.create(eleve=self.eleve, nom="Entreprise de test")
        self.assertEqual(entreprise.eleve, self.eleve)
        self.assertEqual(entreprise.nom, "Entreprise de test")
        self.assertEqual(entreprise.statut, Statut.A_CONTACTER)
        self.assertIsNotNone(entreprise.date_creation)
        self.assertIsNotNone(entreprise.date_modification)

    def test_str_historique_contient_ancien_et_nouveau_statut(self):
        entreprise = Entreprise.objects.create(eleve=self.eleve, nom="ACME")
        historique = HistoriqueStatut.objects.create(
            entreprise=entreprise,
            ancien_statut=Statut.A_CONTACTER,
            nouveau_statut=Statut.A_RELANCER,
            auteur=self.eleve,
        )
        self.assertIn(Statut.A_CONTACTER, str(historique))
        self.assertIn(Statut.A_RELANCER, str(historique))

    def test_historique_est_trie_du_plus_recent_au_plus_ancien(self):
        self.assertEqual(HistoriqueStatut._meta.ordering, ["-date_changement"])

    def test_historique_accepte_une_creation_sans_ancien_statut(self):
        entreprise = Entreprise.objects.create(eleve=self.eleve, nom="Nouvelle")
        historique = HistoriqueStatut.objects.create(
            entreprise=entreprise,
            ancien_statut="",
            nouveau_statut=Statut.A_CONTACTER,
            auteur=self.eleve,
        )
        self.assertEqual(historique.ancien_statut, "")
