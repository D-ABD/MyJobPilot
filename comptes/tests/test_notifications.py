from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, Notification, TypeNotification, Utilisateur
from comptes.notifications import creer_notification


class NotificationTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(
            centre=self.centre,
            nom="BTS SIO",
        )
        self.user = Utilisateur.objects.create_user(
            username="notifications_user",
            password="test-password",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )
        self.autre = Utilisateur.objects.create_user(
            username="notifications_autre",
            password="test-password",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def test_creer_notification_enregistre_le_lien_et_le_type(self):
        notification = creer_notification(
            self.user,
            TypeNotification.COMMENTAIRE,
            "Nouveau commentaire",
            "/entreprises/1/",
        )
        self.assertEqual(notification.destinataire, self.user)
        self.assertEqual(notification.type, TypeNotification.COMMENTAIRE)
        self.assertEqual(notification.lien, "/entreprises/1/")
        self.assertFalse(notification.lu)

    def test_creer_notification_ignore_un_destinataire_inactif(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(
            creer_notification(self.user, TypeNotification.COMMENTAIRE, "Message")
        )
        self.assertFalse(Notification.objects.exists())

    def test_liste_et_compteur_sont_isoles_par_destinataire(self):
        propre = Notification.objects.create(
            destinataire=self.user,
            type=TypeNotification.COMMENTAIRE,
            message="À lire",
        )
        Notification.objects.create(
            destinataire=self.autre,
            type=TypeNotification.COMMENTAIRE,
            message="Privée",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("comptes:notifications"))
        compteur = self.client.get(reverse("comptes:notifications_unread_count"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["notifications"]), [propre])
        self.assertEqual(compteur.json(), {"count": 1})

    def test_marquer_lue_ne_modifie_que_la_notification_propre(self):
        propre = Notification.objects.create(
            destinataire=self.user,
            type=TypeNotification.COMMENTAIRE,
            message="À lire",
        )
        autre = Notification.objects.create(
            destinataire=self.autre,
            type=TypeNotification.COMMENTAIRE,
            message="Privée",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("comptes:notification_mark_read", args=[propre.pk])
        )

        self.assertEqual(response.status_code, 302)
        propre.refresh_from_db()
        autre.refresh_from_db()
        self.assertTrue(propre.lu)
        self.assertFalse(autre.lu)

    def test_marquer_tout_lu_ne_concerne_que_le_destinataire(self):
        Notification.objects.create(
            destinataire=self.user,
            type=TypeNotification.COMMENTAIRE,
            message="À lire",
        )
        autre = Notification.objects.create(
            destinataire=self.autre,
            type=TypeNotification.COMMENTAIRE,
            message="Privée",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("comptes:notification_mark_all_read")
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Notification.objects.filter(destinataire=self.user, lu=False).exists()
        )
        autre.refresh_from_db()
        self.assertFalse(autre.lu)
