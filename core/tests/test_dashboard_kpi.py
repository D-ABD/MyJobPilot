"""Tests des KPI filtrables intégrés aux dashboards staff et admin."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Centre, ScopeSuperviseur, Utilisateur
from entreprises.models import Entreprise, Prospection, Statut


class DashboardsKpiFiltresTests(TestCase):
    def setUp(self):
        self.centre_a = Centre.objects.create(nom="Centre KPI A", departement="75")
        self.centre_b = Centre.objects.create(nom="Centre KPI B", departement="69")
        self.admin = Utilisateur.objects.create_user(
            username="kpi_admin", password="p", role=Utilisateur.Role.ADMIN,
            is_staff=True, is_superuser=True,
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="kpi_sup", password="p", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre_a,
        )
        self.autre_superviseur = Utilisateur.objects.create_user(
            username="kpi_sup_autre", password="p", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre_b,
        )
        self.eleve_a = Utilisateur.objects.create_user(
            username="kpi_eleve_a", password="p", role=Utilisateur.Role.ELEVE,
            centre=self.centre_a,
        )
        self.eleve_a2 = Utilisateur.objects.create_user(
            username="kpi_eleve_a2", password="p", role=Utilisateur.Role.ELEVE,
            centre=self.centre_a,
        )
        self.eleve_b = Utilisateur.objects.create_user(
            username="kpi_eleve_b", password="p", role=Utilisateur.Role.ELEVE,
            centre=self.centre_b,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        ScopeSuperviseur.objects.create(superviseur=self.autre_superviseur, centre=self.centre_b)

    def creer_prospection(self, eleve, nom, statut=Statut.A_CONTACTER, jours_avant=0, relance_jours=None):
        entreprise, _ = Entreprise.objects.get_or_create(nom=nom)
        prospection = Prospection.objects.create(
            eleve=eleve, entreprise=entreprise, statut=statut,
            date_relance=(timezone.localdate() + timedelta(days=relance_jours)) if relance_jours is not None else None,
        )
        if jours_avant:
            Prospection.objects.filter(pk=prospection.pk).update(
                date_creation=timezone.now() - timedelta(days=jours_avant),
            )
            prospection.refresh_from_db()
        return prospection

    def get_staff(self, query=None):
        self.client.force_login(self.superviseur)
        return self.client.get(reverse("staff:dashboard"), query or {})

    def get_admin(self, query=None):
        self.client.force_login(self.admin)
        return self.client.get(reverse("admin_dashboard:dashboard"), query or {})

    def test_dashboard_kpi_accessible_superviseur(self):
        self.assertEqual(self.get_staff().status_code, 200)

    def test_dashboard_kpi_accessible_admin(self):
        self.assertEqual(self.get_admin().status_code, 200)

    def test_dashboard_kpi_interdit_eleve(self):
        self.eleve_a.is_valide = True
        self.eleve_a.save(update_fields=["is_valide"])
        self.client.force_login(self.eleve_a)
        self.assertEqual(self.client.get(reverse("staff:dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin_dashboard:dashboard")).status_code, 403)

    def test_dashboard_kpi_non_connecte_redirige_login(self):
        self.assertEqual(self.client.get(reverse("staff:dashboard")).status_code, 302)
        self.assertEqual(self.client.get(reverse("admin_dashboard:dashboard")).status_code, 302)

    def test_kpi_prospections_par_statut_compte_correctement(self):
        self.creer_prospection(self.eleve_a, "KPI Statut contacter")
        self.creer_prospection(self.eleve_a2, "KPI Statut acceptée", Statut.ACCEPTE)
        result = self.get_admin({"periode": "all"}).context["prospections_par_statut"]
        valeurs = {item["code"]: item["value"] for item in result}
        self.assertEqual(valeurs[Statut.A_CONTACTER], 1)
        self.assertEqual(valeurs[Statut.ACCEPTE], 1)

    def test_kpi_taux_conversion_calcule_correctement(self):
        self.creer_prospection(self.eleve_a, "KPI Conversion acceptée", Statut.ACCEPTE)
        self.creer_prospection(self.eleve_a2, "KPI Conversion en cours", Statut.A_CONTACTER)
        response = self.get_admin({"periode": "all"})
        self.assertEqual(response.context["taux_conversion"], 50)

    def test_kpi_relances_7j_compte_correctement(self):
        self.creer_prospection(self.eleve_a, "KPI Relance proche", Statut.A_RELANCER, relance_jours=3)
        self.creer_prospection(self.eleve_a2, "KPI Relance tardive", Statut.A_RELANCER, relance_jours=8)
        self.creer_prospection(self.eleve_a2, "KPI Relance mauvais statut", Statut.A_CONTACTER, relance_jours=2)
        self.assertEqual(self.get_admin({"periode": "all"}).context["relances_a_venir"], 1)

    def test_kpi_top5_entreprises_trie_et_limite(self):
        self.creer_prospection(self.eleve_a, "KPI Top partagé")
        self.creer_prospection(self.eleve_a2, "KPI Top partagé")
        for index in range(6):
            self.creer_prospection(self.eleve_a, f"KPI Top {index}")
        result = self.get_admin({"periode": "all"}).context["top_entreprises"]
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]["entreprise__nom"], "KPI Top partagé")

    def test_filtre_periode_30j_par_defaut(self):
        response = self.get_admin()
        self.assertEqual(response.context["filtre_periode"], "30")

    def test_filtre_periode_7j_reduit_les_resultats(self):
        self.creer_prospection(self.eleve_a, "KPI récent")
        self.creer_prospection(self.eleve_a2, "KPI ancien", jours_avant=12)
        response = self.get_admin({"periode": "7"})
        self.assertEqual(response.context["prospections_total"], 1)

    def test_scope_superviseur_ne_voit_que_son_scope(self):
        self.creer_prospection(self.eleve_a, "KPI scope dedans")
        self.creer_prospection(self.eleve_b, "KPI scope dehors")
        response = self.get_staff({"periode": "all"})
        self.assertEqual(response.context["prospections_total"], 1)

    def test_scope_admin_voit_tout(self):
        self.creer_prospection(self.eleve_a, "KPI admin A")
        self.creer_prospection(self.eleve_b, "KPI admin B")
        self.assertEqual(self.get_admin({"periode": "all"}).context["prospections_total"], 2)
        response = self.get_admin({
            "superviseur": self.autre_superviseur.pk, "periode": "all",
        })
        self.assertEqual(response.context["prospections_total"], 1)

    def test_filtre_centre_superviseur_restreint_au_scope(self):
        self.creer_prospection(self.eleve_a, "KPI centre autorisé")
        response = self.get_staff({"centre": self.centre_a.pk, "periode": "all"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["prospections_total"], 1)

    def test_filtre_centre_hors_scope_superviseur_est_403(self):
        response = self.get_staff({"centre": self.centre_b.pk})
        self.assertEqual(response.status_code, 403)

    def test_filtre_eleve_superviseur_restreint_au_scope(self):
        self.creer_prospection(self.eleve_a, "KPI élève choisi")
        self.creer_prospection(self.eleve_a2, "KPI élève autre")
        response = self.get_staff({"eleve": self.eleve_a.pk, "periode": "all"})
        self.assertEqual(response.context["prospections_total"], 1)
        self.assertContains(response, "Voir tous les élèves")

    def test_filtre_eleve_admin_fonctionne(self):
        self.creer_prospection(self.eleve_a, "KPI élève admin choisi")
        self.creer_prospection(self.eleve_b, "KPI élève admin autre")
        self.assertEqual(self.get_admin({"eleve": self.eleve_b.pk, "periode": "all"}).context["prospections_total"], 1)

    def test_filtre_superviseur_reserve_admin(self):
        self.creer_prospection(self.eleve_a, "KPI filtre superviseur scope")
        self.creer_prospection(self.eleve_b, "KPI filtre superviseur hors scope")
        response = self.get_staff({"superviseur": self.autre_superviseur.pk, "periode": "all"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["prospections_total"], 1)

    def test_filtres_conserves_dans_url(self):
        response = self.get_admin({"periode": "7", "centre": self.centre_a.pk})
        self.assertEqual(response.wsgi_request.GET["periode"], "7")
        self.assertEqual(response.wsgi_request.GET["centre"], str(self.centre_a.pk))
        self.assertContains(response, 'name="periode"')

    def test_vue_individuelle_eleve_affiche_kpi_de_l_eleve(self):
        response = self.get_admin({"eleve": self.eleve_a.pk})
        self.assertContains(response, "Indicateurs de kpi_eleve_a")
        self.assertContains(response, "Voir tous les élèves")

    def test_kpi_existants_filtres_par_centre(self):
        self.eleve_a.is_valide = True
        self.eleve_a.save(update_fields=["is_valide"])
        response = self.get_admin({"centre": self.centre_a.pk})
        self.assertEqual(response.context["stats"]["eleves_valides"], 1)
        self.assertEqual(response.context["stats"]["eleves_attente"], 1)
        self.assertEqual(response.context["kpis"][0]["value"], 2)

    def test_dashboard_staff_existant_non_casse(self):
        response = self.get_staff()
        self.assertContains(response, "Élèves suivis")
        self.assertContains(response, "Prospections du scope")
        self.assertContains(response, "Taux de validation")
        self.assertContains(response, "Entretiens décrochés")
        self.assertContains(response, "Prospections par statut")
