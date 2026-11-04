from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Centre, Formation, Utilisateur
from entreprises.models import Entreprise, Prospection
from rgpd.models import DemandeRGPD, StatutDemande


class AdminDashboardViewsTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(nom="Centre Paris", defaults={"departement": "75 - Paris"})
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS Test")
        self.admin = Utilisateur.objects.create_user(username="admin_l8a", password="p", role="admin", is_staff=True)
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_l8a", email="eleve@example.com", password="p", role="eleve",
            centre=self.centre, formation=self.formation, is_valide=True,
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="sup_l8a", password="p", role="superviseur", centre=self.centre,
            is_valide=True, is_active=True,
        )

    def test_dashboard_affiche_stats_et_retard(self):
        demande = DemandeRGPD.objects.create(utilisateur=self.eleve, type="acces")
        DemandeRGPD.objects.filter(pk=demande.pk).update(
            date_demande=timezone.now() - timedelta(days=26),
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["eleves_valides"], 1)
        self.assertEqual(response.context["stats"]["demandes_rgpd_retard"], 1)

    def test_admin_eleves_filtre_q_et_centre(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:eleves"), {
            "q": "eleve@example.com", "centre": self.centre.pk, "is_valide": "true",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [self.eleve])

    def test_superviseur_est_cree_avec_scope_initial(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_dashboard:superviseur_create"), {
            "username": "nouveau_sup", "email": "sup@example.com",
            "password": "MotDePasse2026!", "centre": self.centre.pk,
        })
        self.assertEqual(response.status_code, 302)
        nouveau = Utilisateur.objects.get(username="nouveau_sup")
        self.assertTrue(nouveau.scopes.filter(centre=self.centre, is_active=True).exists())

    def test_superviseurs_listee_et_paginee(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:superviseurs"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)

    def test_role_non_admin_refuse_dashboard(self):
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("admin_dashboard:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_compte_prospections_et_demandes_ouvertes(self):
        entreprise = Entreprise.objects.create(nom="Entreprise Lot 8a")
        Prospection.objects.create(eleve=self.eleve, entreprise=entreprise)
        DemandeRGPD.objects.create(utilisateur=self.eleve, type="acces", statut=StatutDemande.EN_COURS)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:dashboard"))
        self.assertEqual(response.context["stats"]["prospections_totales"], 1)
        self.assertEqual(response.context["stats"]["demandes_rgpd_attente"], 1)
