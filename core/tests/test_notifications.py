from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from comptes.models import Centre, Formation, Notification, ScopeSuperviseur, TypeNotification, Utilisateur
from entreprises.models import Entreprise, Prospection, Statut


class NotificationsInAppTests(TestCase):
    def setUp(self):
        self.centre = Centre.objects.create(nom="Centre notifications 21a", departement="75 - Paris")
        self.formation = Formation.objects.create(centre=self.centre, nom="Formation notifications 21a")
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_notif_21a", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.centre, formation=self.formation, is_valide=True,
        )
        self.autre_eleve = Utilisateur.objects.create_user(
            username="autre_eleve_notif_21a", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.centre, formation=self.formation, is_valide=True,
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="superviseur_notif_21a", password="test", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre, is_valide=True,
        )
        self.admin = Utilisateur.objects.create_user(
            username="admin_notif_21a", password="test", role=Utilisateur.Role.ADMIN,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre, is_active=True)
        self.entreprise = Entreprise.objects.create(nom="Entreprise notifications 21a")
        self.prospection = Prospection.objects.create(eleve=self.eleve, entreprise=self.entreprise)
        self.client.force_login(self.eleve)
        self.client_csrf = Client(enforce_csrf_checks=True)
        self.client_csrf.force_login(self.eleve)

    def _csrf_token(self):
        self.client_csrf.get(reverse("comptes:notifications"))
        return self.client_csrf.cookies["csrftoken"].value

    def test_creation_relance_cree_notification_pour_eleve(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(
            reverse("entreprises:changer_statut", args=[self.prospection.pk]),
            {"nouveau_statut": Statut.A_RELANCER, "date_associee": (date.today() + timedelta(days=7)).isoformat()},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.filter(destinataire=self.eleve).count(), 1)
        notification = Notification.objects.get(destinataire=self.eleve)
        self.assertEqual(notification.type, TypeNotification.RELANCE_CREEE)
        self.assertEqual(notification.message, f"Nouvelle relance sur {self.entreprise.nom}")

    def test_changement_statut_par_superviseur_cree_notification(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(
            reverse("entreprises:changer_statut", args=[self.prospection.pk]),
            {"nouveau_statut": Statut.CANDIDATURE_ENVOYEE},
        )

        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(destinataire=self.eleve)
        self.assertEqual(notification.type, TypeNotification.STATUT_CHANGE)
        self.assertIn("Candidature envoyée", notification.message)

    def test_changement_statut_par_eleve_ne_cree_pas_notification(self):
        response = self.client.post(
            reverse("entreprises:changer_statut", args=[self.prospection.pk]),
            {"nouveau_statut": Statut.CANDIDATURE_ENVOYEE},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Notification.objects.exists())

    def test_modification_codes_rome_cree_notification(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(
            reverse("staff:modifier_codes_rome", args=[self.eleve.pk]),
            {"codes_rome": "M1805,I1401"},
        )

        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(destinataire=self.eleve)
        self.assertEqual(notification.type, TypeNotification.CODES_ROME_MODIFIES)
        self.assertEqual(notification.message, "Vos codes ROME ont été mis à jour par votre superviseur")

    def test_liste_notifications_affiche_uniquement_les_siennes(self):
        propre = Notification.objects.create(
            destinataire=self.eleve, type=TypeNotification.STATUT_CHANGE, message="Ma notification",
        )
        Notification.objects.create(
            destinataire=self.autre_eleve, type=TypeNotification.STATUT_CHANGE, message="Notification privée",
        )

        response = self.client.get(reverse("comptes:notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["notifications"]), [propre])
        self.assertContains(response, "Ma notification")
        self.assertNotContains(response, "Notification privée")

    def test_marquer_notification_lue_change_le_statut(self):
        notification = Notification.objects.create(
            destinataire=self.eleve, type=TypeNotification.STATUT_CHANGE,
            message="À lire", lien=f"/entreprises/{self.prospection.pk}/",
        )
        url = reverse("comptes:notification_mark_read", args=[notification.pk])
        token = self._csrf_token()

        self.assertEqual(self.client_csrf.post(url).status_code, 403)
        response = self.client_csrf.post(url, {"csrfmiddlewaretoken": token})

        self.assertRedirects(response, reverse("entreprises:detail", args=[self.prospection.pk]))
        notification.refresh_from_db()
        self.assertTrue(notification.lu)

    def test_marquer_notification_lue_ne_peut_pas_marquer_celle_d_un_autre(self):
        notification = Notification.objects.create(
            destinataire=self.autre_eleve, type=TypeNotification.STATUT_CHANGE, message="Privée",
        )

        response = self.client.post(reverse("comptes:notification_mark_read", args=[notification.pk]))

        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.lu)

    def test_marquer_toutes_lues_met_tout_a_lu(self):
        notifications = [
            Notification.objects.create(
                destinataire=self.eleve, type=TypeNotification.STATUT_CHANGE, message=f"Notif {numero}",
            )
            for numero in range(2)
        ]
        autre = Notification.objects.create(
            destinataire=self.autre_eleve, type=TypeNotification.STATUT_CHANGE, message="Autre compte",
        )
        token = self._csrf_token()
        url = reverse("comptes:notification_mark_all_read")

        self.assertEqual(self.client_csrf.post(url).status_code, 403)
        response = self.client_csrf.post(url, {"csrfmiddlewaretoken": token})

        self.assertRedirects(response, reverse("comptes:notifications"))
        self.assertFalse(Notification.objects.filter(destinataire=self.eleve, lu=False).exists())
        autre.refresh_from_db()
        self.assertFalse(autre.lu)
        self.assertTrue(all(Notification.objects.get(pk=item.pk).lu for item in notifications))

    def test_compteur_notifications_non_lues_dans_navbar(self):
        Notification.objects.create(
            destinataire=self.eleve, type=TypeNotification.STATUT_CHANGE, message="Non lue 1",
        )
        Notification.objects.create(
            destinataire=self.eleve, type=TypeNotification.STATUT_CHANGE, message="Non lue 2",
        )

        response = self.client.get(reverse("comptes:notifications"))

        self.assertEqual(response.context["notifications_non_lues"], 2)
        self.assertContains(response, 'id="notifications-count"')
        self.assertContains(response, 'id="notifications-count-mobile"')
        self.assertContains(response, "bi-bell")

    def test_cloche_navbar_masquee_si_non_connecte(self):
        response = Client().get(reverse("comptes:notifications"))

        self.assertEqual(response.status_code, 302)
        accueil = Client().get(reverse("comptes:accueil"))
        self.assertNotContains(accueil, "bi-bell")

    def test_liste_notifications_pagine_20_par_page(self):
        Notification.objects.bulk_create([
            Notification(
                destinataire=self.eleve,
                type=TypeNotification.STATUT_CHANGE,
                message=f"Notification {numero}",
            )
            for numero in range(23)
        ])

        response = self.client.get(reverse("comptes:notifications"), {"page": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["notifications"]), 3)

    def test_liste_notifications_non_connecte_redirige_login(self):
        response = Client().get(reverse("comptes:notifications"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)
