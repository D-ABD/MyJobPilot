from django.test import TestCase
from django.urls import reverse

from comptes.models import Notification, TypeNotification, Utilisateur
from entreprises.models import Entreprise, Prospection, Statut


class NotificationsProgressionDashboardTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="dashboard-notifications-progression", password="test",
            role=Utilisateur.Role.ELEVE, is_valide=True,
        )
        for index in range(5):
            Prospection.objects.create(
                eleve=self.eleve,
                entreprise=Entreprise.objects.create(nom=f"Dashboard notification {index}"),
                statut=Statut.A_RELANCER,
            )

    def test_dashboard_eleve_cree_notifications_progression(self):
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:dashboard"))

        self.assertEqual(response.status_code, 200)
        notifications = Notification.objects.filter(
            destinataire=self.eleve,
            type=TypeNotification.PROGRESSION_BADGE,
        )
        self.assertEqual(notifications.count(), 3)
