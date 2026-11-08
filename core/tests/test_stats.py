"""Tests des indicateurs et de l'isolation des cockpits par rôle."""
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from comptes.models import Centre, ScopeSuperviseur, Utilisateur
from core.stats import calculer_stats_admin, calculer_stats_eleve, calculer_stats_superviseur
from entreprises.models import Entreprise, Prospection, Statut
from rgpd.models import DemandeRGPD, StatutDemande, TypeDemande


class StatsCockpitsTests(TestCase):
    def setUp(self):
        self.paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris", defaults={"departement": "75 - Paris"}
        )
        self.lyon, _ = Centre.objects.get_or_create(
            nom="Centre Cockpit Lyon", defaults={"departement": "69 - Rhône"}
        )
        self.eleve = Utilisateur.objects.create_user(
            username="cockpit_eleve", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.paris, is_valide=True,
        )
        self.autre_eleve = Utilisateur.objects.create_user(
            username="cockpit_autre", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.lyon,
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="cockpit_staff", password="test", role=Utilisateur.Role.SUPERVISEUR,
            is_valide=True,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.paris)
        self.admin = Utilisateur.objects.create_superuser(
            username="cockpit_admin", email="cockpit-admin@example.com", password="test"
        )

    def creer_prospection(self, eleve, nom, statut=Statut.A_CONTACTER, semaines_avant=None):
        prospect = Prospection.objects.create(
            eleve=eleve, entreprise=Entreprise.objects.create(nom=nom), statut=statut
        )
        if semaines_avant is not None:
            cible = timezone.localdate() - timedelta(weeks=semaines_avant)
            cible = cible - timedelta(days=cible.weekday()) + timedelta(days=2)
            date_aware = timezone.make_aware(datetime.combine(cible, datetime.min.time()))
            Prospection.objects.filter(pk=prospect.pk).update(date_creation=date_aware)
            prospect.refresh_from_db()
        return prospect

    def test_eleve_stats_isolees_et_kpis(self):
        self.creer_prospection(self.eleve, "Cockpit candidature", Statut.CANDIDATURE_ENVOYEE)
        self.creer_prospection(self.eleve, "Cockpit entretien", Statut.ENTRETIEN_PROGRAMME)
        self.creer_prospection(self.autre_eleve, "Cockpit externe")

        stats = calculer_stats_eleve(self.eleve)

        self.assertEqual([k["value"] for k in stats["kpis"][:3]], [2, 1, 1])
        self.assertEqual(sum(stats["charts"]["statuts"]["data"]), 2)
        self.assertEqual(sum(stats["charts"]["activite"]["data"]), 2)

    def test_courbe_hebdomadaire_garde_toujours_8_semaines_et_zeros(self):
        self.creer_prospection(self.eleve, "Cockpit semaine quatre", semaines_avant=4)

        serie = calculer_stats_eleve(self.eleve)["charts"]["activite"]

        self.assertEqual(serie["labels"], ["S-7", "S-6", "S-5", "S-4", "S-3", "S-2", "S-1", "Cette semaine"])
        self.assertEqual(len(serie["data"]), 8)
        self.assertEqual(sum(serie["data"]), 1)
        self.assertGreater(serie["data"].count(0), 0)

    def test_superviseur_stats_limitees_aux_eleves_du_scope(self):
        self.creer_prospection(self.eleve, "Cockpit dans scope", Statut.ENTRETIEN_PROGRAMME)
        self.creer_prospection(self.autre_eleve, "Cockpit hors scope")

        stats = calculer_stats_superviseur(self.superviseur)

        self.assertEqual(stats["kpis"][0]["value"], 1)
        self.assertEqual(stats["kpis"][1]["value"], 1)
        self.assertEqual(stats["kpis"][3]["value"], 1)
        self.assertEqual(sum(stats["charts"]["statuts"]["data"]), 1)

    def test_superviseur_courbe_a_8_labels_meme_scope_vide(self):
        stats = calculer_stats_superviseur(self.superviseur)
        serie = stats["charts"]["activite"]
        self.assertEqual(len(serie["labels"]), 8)
        self.assertEqual(len(serie["data"]), 8)
        self.assertEqual(serie["data"], [0] * 8)

    def test_admin_stats_et_series_mensuelles_globales(self):
        self.creer_prospection(self.eleve, "Cockpit élève")
        self.creer_prospection(self.autre_eleve, "Cockpit autre")
        DemandeRGPD.objects.create(
            utilisateur=self.eleve, type=TypeDemande.ACCES, statut=StatutDemande.RECUE
        )

        stats = calculer_stats_admin()

        self.assertEqual(stats["kpis"][0]["value"], 2)
        self.assertEqual(stats["kpis"][1]["value"], 1)
        self.assertEqual(sum(stats["charts"]["statuts"]["data"]), 2)
        self.assertEqual(len(stats["charts"]["prospections_mois"]["labels"]), 12)
        self.assertEqual(len(stats["charts"]["demandes_mois"]["data"]), 12)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_dashboards_rendent_les_kpi_en_html_avec_les_graphiques_en_bonus(self):
        self.creer_prospection(self.eleve, "Cockpit rendu")
        self.client.force_login(self.eleve)
        reponse_eleve = self.client.get(reverse("entreprises:dashboard"))
        self.assertContains(reponse_eleve, "Total de mes prospections")
        self.assertContains(reponse_eleve, 'id="cockpit-chart-data"')

        self.client.force_login(self.superviseur)
        reponse_staff = self.client.get(reverse("staff:dashboard"))
        self.assertContains(reponse_staff, "Élèves suivis")

        self.client.force_login(self.admin)
        reponse_admin = self.client.get(reverse("admin_dashboard:dashboard"))
        self.assertContains(reponse_admin, "Total entreprises")

    def test_terminee_n_est_pas_comptee_comme_une_reponse(self):
        self.creer_prospection(self.eleve, "Stat terminée exclue", Statut.TERMINEE)
        self.creer_prospection(self.eleve, "Stat refus réponse", Statut.REFUS)

        stats = calculer_stats_eleve(self.eleve)

        taux = next(kpi["value"] for kpi in stats["kpis"] if kpi["label"] == "Taux de réponse")
        self.assertEqual(taux, "50%")

