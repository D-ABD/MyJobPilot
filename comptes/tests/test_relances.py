"""Tests des relances élève et de leur traitement automatique."""
import os
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from comptes.models import Centre, JournalAction, Utilisateur
from entreprises.models import Entreprise, HistoriqueStatut, Prospection, Statut


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RelancesTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris", defaults={"departement": "75 - Paris"},
        )
        self.eleve = Utilisateur.objects.create_user(
            username="relance_eleve", password="motdepasse", email="relance@example.com",
            first_name="Camille", role=Utilisateur.Role.ELEVE,
            centre=self.centre, is_valide=True,
        )
        self.autre_eleve = Utilisateur.objects.create_user(
            username="relance_autre", password="motdepasse", email="autre@example.com",
            role=Utilisateur.Role.ELEVE, centre=self.centre, is_valide=True,
        )

    def creer_prospection(self, eleve=None, *, jours=8, statut=Statut.A_RELANCER, **kwargs):
        eleve = eleve or self.eleve
        entreprise = Entreprise.objects.create(
            nom=f"Entreprise relance {eleve.pk} {Prospection.objects.count()}",
            ville="Paris",
        )
        return Prospection.objects.create(
            eleve=eleve,
            entreprise=entreprise,
            statut=statut,
            date_relance=timezone.localdate() - timedelta(days=jours),
            **kwargs,
        )

    def test_mes_relances_liste_et_isolation(self):
        visible = self.creer_prospection()
        autre = self.creer_prospection(self.autre_eleve)
        future = self.creer_prospection(jours=-1)
        ancienne_candidature = self.creer_prospection(statut=Statut.CANDIDATURE_ENVOYEE)
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:mes_relances"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En retard")
        self.assertContains(response, "À venir")
        self.assertContains(response, visible.entreprise.nom)
        self.assertNotContains(response, autre.entreprise.nom)
        self.assertContains(response, future.entreprise.nom)
        self.assertNotContains(response, ancienne_candidature.entreprise.nom)

    def test_mes_relances_a_venir(self):
        a_venir = self.creer_prospection(jours=-5)
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:mes_relances"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "À venir")
        self.assertContains(response, a_venir.entreprise.nom)
        self.assertContains(response, "Dans 5 jours")

    def test_mes_relances_compteur(self):
        self.creer_prospection(jours=8)
        self.creer_prospection(jours=-5)
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:mes_relances_compteur"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["en_retard"], 1)

    def test_mes_relances_compteur_json(self):
        self.creer_prospection(jours=8)
        self.creer_prospection(jours=-5)
        self.creer_prospection(jours=0)
        self.creer_prospection(jours=-30)
        self.creer_prospection(jours=-31)
        self.creer_prospection(jours=-40)
        self.creer_prospection(self.autre_eleve)
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:mes_relances_compteur"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"en_retard": 1, "a_venir": 3, "total": 4})

    def test_mes_relances_pas_de_bouton_terminer_pour_a_venir(self):
        a_venir = self.creer_prospection(jours=-5)
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:mes_relances"))

        self.assertContains(response, a_venir.entreprise.nom)
        self.assertNotContains(response, "Terminer la relance")
        self.assertContains(response, "Voir la prospection")

    def test_mes_relances_accessible_pour_admin(self):
        admin = Utilisateur.objects.create_superuser(
            username="relance_admin", email="admin@example.com", password="motdepasse",
        )
        prospection = self.creer_prospection(admin)
        self.client.force_login(admin)

        response = self.client.get(reverse("entreprises:mes_relances"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, prospection.entreprise.nom)
        self.assertContains(response, "Mes relances")
        self.assertEqual(self.client.get(reverse("entreprises:mes_relances_compteur")).status_code, 200)

    def test_mes_relances_accessible_pour_superviseur(self):
        superviseur = Utilisateur.objects.create_user(
            username="relance_superviseur", password="motdepasse",
            role=Utilisateur.Role.SUPERVISEUR, centre=self.centre, is_valide=True,
        )
        prospection = self.creer_prospection(superviseur)
        autre_prospection = self.creer_prospection()
        self.client.force_login(superviseur)

        response = self.client.get(reverse("entreprises:mes_relances"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, prospection.entreprise.nom)
        self.assertContains(response, "Mes relances")
        self.assertNotContains(response, autre_prospection.entreprise.nom)

    def test_compteur_relances_pour_superviseur(self):
        superviseur = Utilisateur.objects.create_user(
            username="relance_superviseur_compteur", password="motdepasse",
            role=Utilisateur.Role.SUPERVISEUR, centre=self.centre, is_valide=True,
        )
        self.creer_prospection(superviseur, jours=8)
        self.creer_prospection(superviseur, jours=-5)
        self.creer_prospection(jours=8)
        self.client.force_login(superviseur)

        response = self.client.get(reverse("entreprises:mes_relances_compteur"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"en_retard": 1, "a_venir": 1, "total": 2})

    def test_terminer_relance_met_a_jour_statut_date_historique_et_journal(self):
        prospection = self.creer_prospection()
        self.client.force_login(self.eleve)

        response = self.client.post(reverse("entreprises:mes_relances_terminer", args=[prospection.pk]))

        self.assertRedirects(response, reverse("entreprises:mes_relances"))
        prospection.refresh_from_db()
        self.assertEqual(prospection.statut, Statut.CANDIDATURE_ENVOYEE)
        self.assertEqual(prospection.date_candidature, timezone.localdate())
        self.assertTrue(HistoriqueStatut.objects.filter(
            prospection=prospection,
            ancien_statut=Statut.A_RELANCER,
            nouveau_statut=Statut.CANDIDATURE_ENVOYEE,
            auteur=self.eleve,
            date_associee=timezone.localdate(),
        ).exists())
        self.assertTrue(JournalAction.objects.filter(
            utilisateur=self.eleve,
            action=JournalAction.Action.CHANGEMENT_STATUT,
            cible_id=str(prospection.pk),
        ).exists())

    @patch.dict(os.environ, {"RELANCES_AUTO_JOURS": "7", "RELANCES_AUTO_EMAIL": "True"})
    def test_relancer_prospections_dry_run_ne_modifie_rien(self):
        prospection = self.creer_prospection()
        sortie = StringIO()

        call_command("relancer_prospections", dry_run=True, stdout=sortie)

        prospection.refresh_from_db()
        self.assertIn("seraient envoyés", sortie.getvalue())
        self.assertEqual(mail.outbox, [])
        self.assertIsNone(prospection.date_derniere_relance_email)
        self.assertFalse(JournalAction.objects.filter(
            action=JournalAction.Action.RELANCE_EMAIL_ENVOYE,
        ).exists())

    @patch.dict(os.environ, {"RELANCES_AUTO_JOURS": "7", "RELANCES_AUTO_EMAIL": "True"})
    def test_relancer_prospections_envoie_email_et_journalise(self):
        prospection = self.creer_prospection()

        call_command("relancer_prospections", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.eleve.email])
        self.assertIn(prospection.entreprise.nom, mail.outbox[0].body)
        self.assertIn("/mes-relances/", mail.outbox[0].alternatives[0][0])
        prospection.refresh_from_db()
        self.assertIsNotNone(prospection.date_derniere_relance_email)
        self.assertTrue(JournalAction.objects.filter(
            utilisateur=self.eleve,
            action=JournalAction.Action.RELANCE_EMAIL_ENVOYE,
            details={"prospection_id": prospection.pk, "eleve_id": self.eleve.pk},
        ).exists())

    @patch.dict(os.environ, {"RELANCES_AUTO_JOURS": "7", "RELANCES_AUTO_EMAIL": "True"})
    def test_relancer_prospections_ne_renvoie_pas_de_doublon(self):
        prospection = self.creer_prospection()

        call_command("relancer_prospections", stdout=StringIO())
        call_command("relancer_prospections", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(JournalAction.objects.filter(
            action=JournalAction.Action.RELANCE_EMAIL_ENVOYE,
            cible_id=str(prospection.pk),
        ).count(), 1)

    @patch.dict(os.environ, {"RELANCES_AUTO_JOURS": "7", "RELANCES_AUTO_EMAIL": "False"})
    def test_relancer_prospections_peut_etre_desactivee(self):
        prospection = self.creer_prospection()

        call_command("relancer_prospections", stdout=StringIO())

        self.assertEqual(mail.outbox, [])
        prospection.refresh_from_db()
        self.assertIsNone(prospection.date_derniere_relance_email)
