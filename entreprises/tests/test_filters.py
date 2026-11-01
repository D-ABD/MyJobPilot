"""Tests unitaires du FiltreMixin appliqué aux prospections."""
from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone

from comptes.models import Centre, Formation, Utilisateur
from core.filters import FiltreMixin
from entreprises.models import Entreprise, Prospection, Statut


class FiltreMixinTests(TestCase):
    def setUp(self):
        centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        formation, _ = Formation.objects.get_or_create(centre=centre, nom="BTS SIO")
        self.eleve = Utilisateur.objects.create_user(
            username="filtre_prospection",
            password="mot-de-passe-test",
            role=Utilisateur.Role.ELEVE,
            centre=centre,
            formation=formation,
            is_valide=True,
        )
        entreprise_acme = Entreprise.objects.create(
            nom="ACME Corp",
            secteur="Conseil",
            ville="Paris",
            contact_nom="Émilie",
            contact_email="contact@acme.test",
        )
        entreprise_beta = Entreprise.objects.create(
            nom="Beta Services",
            secteur="Informatique",
            ville="Lyon",
        )
        self.acme = Prospection.objects.create(eleve=self.eleve, entreprise=entreprise_acme)
        self.beta = Prospection.objects.create(
            eleve=self.eleve,
            entreprise=entreprise_beta,
            statut=Statut.A_RELANCER,
        )
        instant = timezone.now()
        Prospection.objects.filter(pk=self.acme.pk).update(date_modification=instant - timedelta(days=10))
        Prospection.objects.filter(pk=self.beta.pk).update(date_modification=instant)
        self.filtreur = FiltreMixin()
        self.queryset = Prospection.objects.filter(eleve=self.eleve).select_related("entreprise")

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

    def test_recherche_insensible_a_la_casse_dans_entreprise_liee(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"q": "acme"})
        self.assertEqual(list(resultats), [self.acme])

    def test_recherche_ne_normalise_pas_les_accents(self):
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

    def test_tri_nom_entreprise_ascendant(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"tri": "entreprise__nom", "ordre": "asc"})
        self.assertEqual(list(resultats), [self.acme, self.beta])

    def test_tri_nom_entreprise_descendant(self):
        resultats = self.filtreur.apply_filters(self.queryset, {"tri": "-entreprise__nom", "ordre": "desc"})
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
            "/dashboard/?statut=a_contacter&date_debut=2026-01-01&date_fin=2026-01-31&q=acme&tri=entreprise__nom&ordre=asc"
        )
        contexte = self.filtreur.get_contexte_filtres(request)
        self.assertEqual(contexte["filtre_statut"], Statut.A_CONTACTER)
        self.assertEqual(contexte["filtre_date_debut"], "2026-01-01")
        self.assertEqual(contexte["filtre_date_fin"], "2026-01-31")
        self.assertEqual(contexte["filtre_q"], "acme")
        self.assertEqual(contexte["filtre_tri"], "entreprise__nom")
        self.assertEqual(contexte["filtre_ordre"], "asc")
        self.assertEqual(contexte["url_reset"], "/dashboard/")
