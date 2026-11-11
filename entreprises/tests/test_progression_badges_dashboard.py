from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Utilisateur
from core.models import Badge, BadgeObtenu, Tache
from entreprises.models import Entreprise, Prospection, Statut


class ProgressionBadgesDashboardTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="dashboard-progression-eleve", password="test",
            role=Utilisateur.Role.ELEVE, is_valide=True,
        )
        self.client.force_login(self.eleve)

    def test_dashboard_eleve_affiche_les_trois_blocs(self):
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "📋 Prospections")
        self.assertContains(response, "📝 Candidatures")
        self.assertContains(response, "🔄 Relances")

    def test_dashboard_eleve_affiche_prochain_badge_et_progression(self):
        for index in range(25):
            Prospection.objects.create(
                eleve=self.eleve,
                entreprise=Entreprise.objects.create(nom=f"Prospection progression {index}"),
                statut=Statut.A_RELANCER,
            )

        response = self.client.get(reverse("entreprises:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Persévérant")
        self.assertContains(response, "25 / 35")
        self.assertContains(response, "Il manque 10 pour Persévérant")

    def test_dashboard_eleve_affiche_les_derniers_badges(self):
        badge = Badge.objects.create(
            slug="dashboard-dernier-badge", categorie=Badge.Categorie.SUIVI,
            nom="Badge récent sur le dashboard",
            type_condition=Badge.TypeCondition.RELANCES_COUNT,
        )
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        Tache.objects.create(
            titre="Préparer une candidature",
            createur=self.eleve,
            assigne_a=self.eleve,
            date_echeance=timezone.localdate(),
            statut=Tache.Statut.EN_COURS,
        )

        response = self.client.get(reverse("entreprises:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Badge récent sur le dashboard")
        self.assertContains(response, reverse("core:mes_badges"))
        self.assertContains(response, "Mes tâches (1)")
        self.assertContains(response, "Préparer une candidature")
        contenu = response.content.decode()
        self.assertLess(contenu.index("Derniers badges obtenus"), contenu.index("titre-taches-dashboard"))
        self.assertLess(contenu.index("titre-taches-dashboard"), contenu.index("titre-graphiques-eleve"))
