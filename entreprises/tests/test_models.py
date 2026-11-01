"""Tests des modèles Entreprise, Prospection et HistoriqueStatut."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from comptes.models import Centre, Formation, Utilisateur
from entreprises.models import Entreprise, HistoriqueStatut, Prospection, Statut


class ModelesEntreprisesTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS SIO")
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_modeles",
            password="mot-de-passe-test",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def creer_entreprise(self, nom="ACME"):
        return Entreprise.objects.create(nom=nom)

    def creer_prospection(self, nom="ACME", eleve=None):
        entreprise = self.creer_entreprise(nom)
        return Prospection.objects.create(eleve=eleve or self.eleve, entreprise=entreprise)

    def test_statut_prospection_par_defaut_est_a_contacter(self):
        prospection = self.creer_prospection()
        self.assertEqual(prospection.statut, Statut.A_CONTACTER)

    def test_str_entreprise_retourne_son_nom(self):
        entreprise = self.creer_entreprise()
        self.assertEqual(str(entreprise), "ACME")

    def test_entreprise_est_un_referentiel_sans_donnees_de_prospection(self):
        entreprise = self.creer_entreprise("Entreprise de test")
        self.assertEqual(entreprise.nom, "Entreprise de test")
        self.assertIsNotNone(entreprise.date_creation)
        self.assertFalse(hasattr(entreprise, "statut"))
        self.assertFalse(hasattr(entreprise, "eleve"))

    def test_un_eleve_ne_peut_avoir_quune_prospection_par_entreprise(self):
        entreprise = self.creer_entreprise()
        Prospection.objects.create(eleve=self.eleve, entreprise=entreprise)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Prospection.objects.create(eleve=self.eleve, entreprise=entreprise)

    def test_plusieurs_eleves_peuvent_prospecter_la_meme_entreprise(self):
        entreprise = self.creer_entreprise()
        autre_eleve = Utilisateur.objects.create_user(
            username="autre_eleve_modeles",
            password="mot-de-passe-test",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
        )
        premiere = Prospection.objects.create(eleve=self.eleve, entreprise=entreprise)
        seconde = Prospection.objects.create(eleve=autre_eleve, entreprise=entreprise)
        self.assertEqual(entreprise.prospections.count(), 2)
        self.assertNotEqual(premiere.pk, seconde.pk)

    def test_nom_entreprise_est_unique_sans_tenir_compte_de_la_casse(self):
        self.creer_entreprise("ACME Corp")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Entreprise.objects.create(nom="acme corp")

    def test_str_prospection_contient_eleve_et_entreprise(self):
        prospection = self.creer_prospection()
        self.assertEqual(str(prospection), "eleve_modeles → ACME")

    def test_str_historique_contient_ancien_et_nouveau_statut(self):
        prospection = self.creer_prospection()
        historique = HistoriqueStatut.objects.create(
            prospection=prospection,
            ancien_statut=Statut.A_CONTACTER,
            nouveau_statut=Statut.A_RELANCER,
            auteur=self.eleve,
        )
        self.assertIn(Statut.A_CONTACTER, str(historique))
        self.assertIn(Statut.A_RELANCER, str(historique))
        self.assertIn("ACME", str(historique))

    def test_historique_est_trie_du_plus_recent_au_plus_ancien(self):
        self.assertEqual(HistoriqueStatut._meta.ordering, ["-date_changement"])

    def test_historique_accepte_une_creation_sans_ancien_statut(self):
        prospection = self.creer_prospection("Nouvelle")
        historique = HistoriqueStatut.objects.create(
            prospection=prospection,
            ancien_statut="",
            nouveau_statut=Statut.A_CONTACTER,
            auteur=self.eleve,
        )
        self.assertEqual(historique.ancien_statut, "")
