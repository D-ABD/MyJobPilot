"""Tests unitaires du FiltreMixin."""
from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone

from comptes.models import Centre, Formation, Utilisateur
from core.filters import FiltreMixin
from entreprises.models import Entreprise, Statut


class FiltreMixinTests(TestCase):
    def setUp(self):
        centre = Centre.objects.create(nom="Centre filtres", departement="75 - Paris")
        formation = Formation.objects.create(centre=centre, nom="BTS Test")
        self.eleve = Utilisateur.objects.create_user(
            username="filtre",
            password="mot-de-passe-test",
            role=Utilisateur.Role.ELEVE,
            centre=centre,
            formation=formation,
            is_valide=True,
        )
        self.acme = Entreprise.objects.create(
            eleve=self.eleve,
            nom="ACME Corp",
            secteur="Conseil",
            ville="Paris",
            contact_nom="Émilie",
            contact_email="contact@acme.test",
        )
        self.beta = Entreprise.objects.create(
            eleve=self.eleve,
            nom="Beta Services",
            secteur="Informatique",
            ville="Lyon",
            statut=Statut.A_RELANCER,
        )
        instant = timezone.now()
        Entreprise.objects.filter(pk=self.acme.pk).update(date_modification=instant - timedelta(days=10))
        Entreprise.objects.filter(pk=self.beta.pk).update(date_modification=instant)
        self.filtreur = FiltreMixin()
        self.queryset = Entreprise.objects.filter(eleve=self.eleve)

    def test_filtre_par_statut(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"statut": Statut.A_CONTACTER})
        self.assertEqual(list(resultats), [self.acme])

    def test_statut_tous_ne_filtre_pas(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"statut": "tous"})
        self.assertEqual(resultats.count(), 2)

    def test_filtre_par_plage_de_dates(self):
        aujourd_hui = timezone.localdate()
        resultats = self.filtreur.apply_filters(
            self.queryset,
            {"date_debut": aujourd_hui.isoformat(), "date_fin": aujourd_hui.isoformat()},
        )
        self.assertEqual(list(resultats), [self.beta])

    def test_recherche_insensible_a_la_casse(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"q": "acme"})
        self.assertEqual(list(resultats), [self.acme])

    def test_recherche_ne_necessite_pas_de_normalisation_des_accents(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"q": "emilie"})
        self.assertEqual(resultats.count(), 0)

    def test_recherche_avec_accent_ne_declenche_pas_d_erreur(self):
        self.filtreur.apply_filters(self.queryset, {"q": "é"})

    def test_combinaison_statut_recherche_et_dates(self):
        aujourd_hui = timezone.localdate()
        resultats = self.filtreur.apply_filters(
            self.queryset,
            {
                "statut": Statut.A_RELANCER,
                "q": "BETA",
                "date_debut": aujourd_hui.isoformat(),
                "date_fin": aujourd_hui.isoformat(),
            },
        )
        self.assertEqual(list(resultats), [self.beta])

    def test_tri_nom_ascendant(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"tri": "nom", "ordre": "asc"})
        self.assertEqual(list(resultats), [self.acme, self.beta])

    def test_tri_nom_descendant(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"tri": "-nom", "ordre": "desc"})
        self.assertEqual(list(resultats), [self.beta, self.acme])

    def test_tri_invalide_est_ignore(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"tri": "eleve__username"})
        self.assertEqual(resultats.query.order_by, ())

    def test_recherche_vide_ne_filtre_pas(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"q": "  "})
        self.assertEqual(resultats.count(), 2)

    def test_reset_url_retourne_le_chemin_sans_query_string(self):
        request = RequestFactory().get("/dashboard/?statut=a_contacter&page=2")
        self.assertEqual(self.filtreur.reset_url(request), "/dashboard/")

    def test_contexte_reprend_les_filtres_actuels(self):
        request = RequestFactory().get(
            "/dashboard/?statut=a_contacter&date_debut=2026-01-01&date_fin=2026-01-31&q=acme&tri=nom&ordre=asc"
        )
        contexte = self.filtreur.get_contexte_filtres(request)
        self.assertEqual(contexte["filtre_statut"], Statut.A_CONTACTER)
        self.assertEqual(contexte["filtre_date_debut"], "2026-01-01")
        self.assertEqual(contexte["filtre_date_fin"], "2026-01-31")
        self.assertEqual(contexte["filtre_q"], "acme")
        self.assertEqual(contexte["filtre_tri"], "nom")
        self.assertEqual(contexte["filtre_ordre"], "asc")
        self.assertEqual(contexte["url_reset"], "/dashboard/")
