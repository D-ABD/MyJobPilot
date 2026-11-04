from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from django.contrib.sessions.models import Session
from comptes.models import Centre, Formation, JournalAction, Utilisateur
from entreprises.models import Commentaire, Entreprise, HistoriqueStatut, Prospection, Statut
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


    def _creer_prospection(self):
        entreprise = Entreprise.objects.create(nom="Prospection admin detail")
        return Prospection.objects.create(eleve=self.eleve, entreprise=entreprise)

    def test_admin_eleve_detail_accede(self):
        url = reverse("admin_dashboard:eleve_detail", args=[self.eleve.pk])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.eleve)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_eleve_valider(self):
        eleve = Utilisateur.objects.create_user(
            username="eleve_a_valider", password="p", role="eleve",
            centre=self.centre, formation=self.formation, is_valide=False,
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_dashboard:eleve_valider", args=[eleve.pk]))
        self.assertEqual(response.status_code, 302)
        eleve.refresh_from_db()
        self.assertTrue(eleve.is_valide)
        self.assertTrue(timezone.is_aware(eleve.date_validation))
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.COMPTE_VALIDE, cible_id=str(eleve.pk),
        ).exists())

    def test_admin_eleve_refuser(self):
        eleve = Utilisateur.objects.create_user(
            username="eleve_a_refuser", password="p", role="eleve",
            centre=self.centre, formation=self.formation, is_valide=False,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_dashboard:eleve_refuser", args=[eleve.pk]),
            {"motif_refus": "Dossier incomplet"},
        )
        self.assertEqual(response.status_code, 302)
        eleve.refresh_from_db()
        self.assertEqual(eleve.motif_refus, "Dossier incomplet")
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.COMPTE_REFUSE, cible_id=str(eleve.pk),
        ).exists())

    def test_admin_eleve_desactiver(self):
        client_eleve = Client()
        client_eleve.force_login(self.eleve)
        session_key = client_eleve.cookies["sessionid"].value
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_dashboard:eleve_desactiver", args=[self.eleve.pk]))
        self.assertEqual(response.status_code, 302)
        self.eleve.refresh_from_db()
        self.assertFalse(self.eleve.is_active)
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.COMPTE_DESACTIVE, cible_id=str(self.eleve.pk),
        ).exists())

    def test_admin_eleve_changer_centre(self):
        centre2, _ = Centre.objects.get_or_create(
            nom="Centre Lyon", defaults={"departement": "69 - Rhône"},
        )
        formation2, _ = Formation.objects.get_or_create(centre=centre2, nom="BTS Lyon")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_dashboard:eleve_changer_centre", args=[self.eleve.pk]),
            {"centre": centre2.pk, "formation": formation2.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.centre, centre2)
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.CHANGEMENT_CENTRE,
            details__nouveau_centre_id=self.eleve.centre_id,
        ).exists())

    def test_admin_prospection_detail_accede(self):
        prospection = self._creer_prospection()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse(
            "admin_dashboard:prospection_detail", args=[prospection.pk],
        )).status_code, 200)

    def test_admin_prospection_changer_statut(self):
        prospection = self._creer_prospection()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_dashboard:prospection_changer_statut", args=[prospection.pk]),
            {"nouveau_statut": Statut.A_RELANCER, "date_associee": timezone.localdate().isoformat(), "commentaire": "Relance"},
        )
        self.assertEqual(response.status_code, 302)
        prospection.refresh_from_db()
        self.assertEqual(prospection.statut, Statut.A_RELANCER)
        self.assertTrue(HistoriqueStatut.objects.filter(
            prospection=prospection, nouveau_statut=Statut.A_RELANCER, auteur=self.admin,
        ).exists())
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.CHANGEMENT_STATUT, cible_id=str(prospection.pk),
        ).exists())

    def test_admin_prospection_ajouter_commentaire(self):
        prospection = self._creer_prospection()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_dashboard:prospection_ajouter_commentaire", args=[prospection.pk]),
            {"contenu": "Retour de l'administration"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Commentaire.objects.filter(
            prospection=prospection, auteur=self.admin, contenu="Retour de l'administration",
        ).exists())
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.COMMENTAIRE_CREE,
            details__prospection_id=prospection.pk,
        ).exists())
