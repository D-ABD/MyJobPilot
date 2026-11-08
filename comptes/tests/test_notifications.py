from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse

from comptes.models import Centre, Formation, Notification, ScopeSuperviseur, TypeNotification, Utilisateur
from comptes.notifications import creer_notification, notifier_ajout_prospection, notifier_changement_statut
from entreprises.models import Entreprise, Prospection


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

    def _prospection(self):
        entreprise = Entreprise.objects.create(nom="Prospection notifications")
        return Prospection.objects.create(eleve=self.user, entreprise=entreprise)

    def _superviseur(self, username):
        user = Utilisateur.objects.create_user(
            username=username, password="test-password", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre, is_valide=True,
        )
        ScopeSuperviseur.objects.create(superviseur=user, centre=self.centre, is_active=True)
        return user

    def test_ajout_prospection_par_eleve_ne_notifie_plus_les_superviseurs(self):
        superviseur = self._superviseur("sup_notif_eleve")
        prospection = self._prospection()
        notifier_ajout_prospection(prospection, self.user)
        self.assertFalse(Notification.objects.filter(destinataire=superviseur, type=TypeNotification.AJOUT_PROSPECTION).exists())
        self.assertFalse(Notification.objects.filter(destinataire=self.user).exists())

    def test_ajout_prospection_par_superviseur_ne_cree_pas_de_notification(self):
        superviseur = self._superviseur("sup_notif_auteur")
        autre = self._superviseur("sup_notif_autre")
        prospection = self._prospection()
        notifier_ajout_prospection(prospection, superviseur)
        self.assertFalse(Notification.objects.filter(type=TypeNotification.AJOUT_PROSPECTION).exists())

    def test_ajout_prospection_par_admin_ne_cree_pas_de_notification(self):
        admin = Utilisateur.objects.create_user(username="admin_notif", password="p", role=Utilisateur.Role.ADMIN)
        superviseur = self._superviseur("sup_notif_admin")
        prospection = self._prospection()
        notifier_ajout_prospection(prospection, admin)
        self.assertFalse(Notification.objects.filter(type=TypeNotification.AJOUT_PROSPECTION).exists())

    def test_ajout_prospection_sans_superviseur_ne_notifie_personne(self):
        prospection = self._prospection()
        notifier_ajout_prospection(prospection, self.user)
        self.assertFalse(Notification.objects.exists())

    def test_changement_statut_par_eleve_notifie_superviseurs(self):
        superviseur = self._superviseur("sup_notif_statut")
        prospection = self._prospection()
        notifier_changement_statut(prospection, self.user, "a_contacter", "a_relancer")
        self.assertFalse(Notification.objects.exists())

    def test_changement_statut_par_eleve_ne_notifie_pas_eleve_lui_meme(self):
        self._superviseur("sup_notif_self")
        prospection = self._prospection()
        notifier_changement_statut(prospection, self.user, "a_contacter", "a_relancer")
        self.assertFalse(Notification.objects.filter(
            destinataire=self.user, type=TypeNotification.STATUT_CHANGE,
        ).exists())

    def test_validation_compte_cree_notification(self):
        from django.contrib import admin
        from comptes.admin import UtilisateurAdmin
        administrateur = Utilisateur.objects.create_user(username="admin_action", password="p", role="admin")
        request = RequestFactory().post("/admin/")
        request.user = administrateur
        UtilisateurAdmin(Utilisateur, admin.site).valider_comptes(request, Utilisateur.objects.filter(pk=self.user.pk))
        self.assertTrue(Notification.objects.filter(destinataire=self.user, type=TypeNotification.COMPTE_VALIDE).exists())

    def test_refus_compte_cree_notification(self):
        from django.contrib import admin
        from comptes.admin import UtilisateurAdmin
        administrateur = Utilisateur.objects.create_user(username="admin_refus_action", password="p", role="admin")
        self.user.motif_refus = "Dossier incomplet"
        self.user.save(update_fields=["motif_refus"])
        request = RequestFactory().post("/admin/")
        request.user = administrateur
        UtilisateurAdmin(Utilisateur, admin.site).refuser_comptes(request, Utilisateur.objects.filter(pk=self.user.pk))
        self.assertTrue(Notification.objects.filter(destinataire=self.user, type=TypeNotification.COMPTE_REFUSE).exists())
