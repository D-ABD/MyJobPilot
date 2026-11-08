from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Centre, Notification, ScopeSuperviseur, TypeNotification, Utilisateur
from core.models import Badge, BadgeObtenu
from entreprises.models import Entreprise, HistoriqueStatut, Prospection, Relance, Statut


class MesRelanceCreerTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre actions relance", defaults={"departement": "75 - Paris"}
        )
        self.eleve = Utilisateur.objects.create_user(
            username="action-relance-eleve", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.centre, email="action-relance@example.com", is_valide=True,
        )
        self.hors_scope = Utilisateur.objects.create_user(
            username="action-relance-hors", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.centre, is_valide=True,
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="action-relance-superviseur", password="test",
            role=Utilisateur.Role.SUPERVISEUR, centre=self.centre, is_valide=True,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre)
        self.admin = Utilisateur.objects.create_user(
            username="action-relance-admin", password="test", role=Utilisateur.Role.ADMIN,
            is_staff=True, is_valide=True,
        )
        self.prospection = self.creer_prospection(self.eleve)

    def creer_prospection(self, eleve, statut=Statut.A_RELANCER):
        return Prospection.objects.create(
            eleve=eleve,
            entreprise=Entreprise.objects.create(nom=f"Entreprise action {eleve.pk} {Prospection.objects.count()}"),
            statut=statut,
            date_relance=timezone.localdate() - timedelta(days=1),
        )

    def poster(self, user, prospection=None, **extras):
        self.client.force_login(user)
        return self.client.post(reverse("entreprises:mes_relance_creer"), {
            "prospection_id": (prospection or self.prospection).pk,
            "type": Relance.Type.PROSPECTION,
            **extras,
        })

    def test_post_cree_une_relance_et_met_a_jour_echeance_et_statut(self):
        nouvelle_date = (timezone.localdate() + timedelta(days=4)).isoformat()
        response = self.poster(self.eleve, date_relance=nouvelle_date, contenu="Appel effectué")
        self.assertRedirects(response, reverse("entreprises:mes_relances"))
        relance = Relance.objects.get(prospection=self.prospection)
        self.assertEqual(relance.contenu, "Appel effectué")
        self.assertEqual(relance.auteur, self.eleve)
        self.prospection.refresh_from_db()
        self.assertEqual(self.prospection.date_relance, date.fromisoformat(nouvelle_date))
        self.assertEqual(self.prospection.statut, Statut.EN_ATTENTE)
        self.assertTrue(HistoriqueStatut.objects.filter(
            prospection=self.prospection, nouveau_statut=Statut.EN_ATTENTE,
        ).exists())

    def test_type_candidature_cree_une_relance_sans_changer_le_statut(self):
        self.client.force_login(self.eleve)
        response = self.client.post(reverse("entreprises:mes_relance_creer"), {
            "prospection_id": self.prospection.pk,
            "type": Relance.Type.CANDIDATURE,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Relance.objects.get(prospection=self.prospection).type, Relance.Type.CANDIDATURE)
        self.prospection.refresh_from_db()
        self.assertEqual(self.prospection.statut, Statut.A_RELANCER)

    def test_post_non_authentifie_redirige_vers_connexion(self):
        response = self.client.post(reverse("entreprises:mes_relance_creer"), {
            "prospection_id": self.prospection.pk, "type": Relance.Type.PROSPECTION,
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    def test_eleve_ne_peut_pas_relancer_la_prospection_d_un_autre(self):
        autre = self.creer_prospection(self.hors_scope)
        response = self.poster(self.eleve, autre)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Relance.objects.filter(prospection=autre).exists())

    def test_superviseur_peut_relancer_pour_un_eleve_dans_son_scope(self):
        response = self.poster(self.superviseur)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Relance.objects.filter(prospection=self.prospection, auteur=self.superviseur).exists())

    def test_superviseur_ne_peut_pas_relancer_hors_scope(self):
        autre_centre = Centre.objects.create(nom="Centre hors scope relance", departement="69 - Rhône")
        autre_eleve = Utilisateur.objects.create_user(
            username="action-relance-autre-centre", password="test", role=Utilisateur.Role.ELEVE,
            centre=autre_centre, is_valide=True,
        )
        autre = self.creer_prospection(autre_eleve)
        response = self.poster(self.superviseur, autre)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Relance.objects.filter(prospection=autre).exists())

    def test_admin_peut_relancer_pour_un_eleve(self):
        response = self.poster(self.admin)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Relance.objects.filter(prospection=self.prospection, auteur=self.admin).exists())

    def test_creation_par_eleve_ne_cree_pas_d_auto_notification(self):
        self.poster(self.eleve)
        self.assertFalse(Notification.objects.filter(
            destinataire=self.eleve, type=TypeNotification.RELANCE_CREEE,
        ).exists())

    def test_creation_par_superviseur_notifie_uniquement_leleve(self):
        self.poster(self.superviseur)
        self.assertTrue(Notification.objects.filter(
            destinataire=self.eleve, type=TypeNotification.RELANCE_CREEE,
        ).exists())
        self.assertFalse(Notification.objects.filter(
            destinataire=self.superviseur, type=TypeNotification.RELANCE_CREEE,
        ).exists())

    def test_creation_par_admin_notifie_uniquement_leleve(self):
        self.poster(self.admin)
        self.assertTrue(Notification.objects.filter(
            destinataire=self.eleve, type=TypeNotification.RELANCE_CREEE,
        ).exists())
        self.assertFalse(Notification.objects.filter(
            destinataire=self.admin, type=TypeNotification.RELANCE_CREEE,
        ).exists())

    def test_action_attribue_le_badge_premiere_relance(self):
        badge = Badge.objects.get(slug="relance-1")
        self.poster(self.eleve)
        self.assertTrue(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_date_relance_vide_efface_lecheance(self):
        self.poster(self.eleve, date_relance="")
        self.prospection.refresh_from_db()
        self.assertIsNone(self.prospection.date_relance)

    def test_terminer_relance_historique_continue_sans_creer_un_evenement_relance(self):
        self.client.force_login(self.eleve)
        response = self.client.post(reverse(
            "entreprises:mes_relances_terminer", args=[self.prospection.pk]
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Relance.objects.filter(prospection=self.prospection).exists())
        self.prospection.refresh_from_db()
        self.assertEqual(self.prospection.statut, Statut.CANDIDATURE_ENVOYEE)
