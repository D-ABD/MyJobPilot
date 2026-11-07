"""Tests des emails transactionnels et de la tolérance aux erreurs SMTP."""
from unittest.mock import patch

from django.contrib import admin
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from comptes.admin import UtilisateurAdmin
from comptes.emails import (
    envoyer_email_accuse_rgpd,
    envoyer_email_refus,
    envoyer_email_reponse_rgpd,
    envoyer_email_validation,
)
from comptes.models import Centre, Utilisateur
from rgpd.models import DemandeRGPD, StatutDemande, TypeDemande


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailsTransactionnelsTests(TestCase):
    def setUp(self):
        self.centre_paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_email_lot13",
            password="MotDePasseEmail13!",
            email="eleve@example.com",
            first_name="Camille",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre_paris,
            is_valide=True,
        )
        self.admin_user = Utilisateur.objects.create_user(
            username="admin_email_lot13",
            password="MotDePasseEmail13!",
            email="admin@example.com",
            role=Utilisateur.Role.ADMIN,
            is_valide=True,
        )
        self.factory = RequestFactory()

    def creer_demande(self, **kwargs):
        defaults = {"utilisateur": self.eleve, "type": TypeDemande.ACCES}
        defaults.update(kwargs)
        return DemandeRGPD.objects.create(**defaults)

    def test_email_validation_envoye(self):
        envoyer_email_validation(self.eleve)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Votre compte MyJobPilot a été validé")
        self.assertEqual(mail.outbox[0].to, [self.eleve.email])
        self.assertIn(self.eleve.username, mail.outbox[0].body)
        self.assertIn("/comptes/connexion/", mail.outbox[0].alternatives[0][0])
        self.assertIn("/confidentialite/", mail.outbox[0].alternatives[0][0])

    def test_email_refus_envoye(self):
        envoyer_email_refus(self.eleve, "Le centre indiqué ne correspond pas.")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Le centre indiqué ne correspond pas.", mail.outbox[0].body)
        self.assertIn("© 2026 MyJobPilot", mail.outbox[0].alternatives[0][0])

    def test_email_accuse_rgpd_envoye(self):
        demande = self.creer_demande()

        envoyer_email_accuse_rgpd(demande)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Accès", mail.outbox[0].body)
        self.assertIn("un mois", mail.outbox[0].body)
        self.assertIn("/confidentialite/", mail.outbox[0].alternatives[0][0])

    def test_email_reponse_rgpd_envoye(self):
        demande = self.creer_demande(
            statut=StatutDemande.REFUSEE,
            motif_refus="La demande ne peut pas être satisfaite.",
        )

        envoyer_email_reponse_rgpd(demande)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Refusée", mail.outbox[0].body)
        self.assertIn("La demande ne peut pas être satisfaite.", mail.outbox[0].body)

    def test_email_non_envoye_si_email_vide(self):
        self.eleve.email = ""
        self.eleve.save(update_fields=["email"])
        demande = self.creer_demande()

        envoyer_email_validation(self.eleve)
        envoyer_email_refus(self.eleve, "Motif")
        envoyer_email_accuse_rgpd(demande)
        envoyer_email_reponse_rgpd(demande)

        self.assertEqual(mail.outbox, [])

    def test_echec_email_validation_et_refus_ne_bloque_pas_action_admin(self):
        utilisateur_admin = UtilisateurAdmin(Utilisateur, admin.site)
        request = self.factory.post("/admin/")
        request.user = self.admin_user
        self.eleve.is_valide = False
        self.eleve.motif_refus = "Motif de refus"
        self.eleve.save(update_fields=["is_valide", "motif_refus"])

        with patch("comptes.admin.envoyer_email_validation", side_effect=RuntimeError("SMTP indisponible")):
            with self.assertLogs("comptes", level="ERROR"):
                utilisateur_admin.valider_comptes(
                    request, Utilisateur.objects.filter(pk=self.eleve.pk),
                )
        self.eleve.refresh_from_db()
        self.assertTrue(self.eleve.is_valide)

        self.eleve.motif_refus = "Motif de refus"
        self.eleve.save(update_fields=["motif_refus"])
        with patch("comptes.admin.envoyer_email_refus", side_effect=RuntimeError("SMTP indisponible")):
            with self.assertLogs("comptes", level="ERROR"):
                utilisateur_admin.refuser_comptes(
                    request, Utilisateur.objects.filter(pk=self.eleve.pk),
                )
        self.eleve.refresh_from_db()
        self.assertFalse(self.eleve.is_valide)

    def test_echec_accuse_rgpd_ne_bloque_pas_creation(self):
        self.client.force_login(self.eleve)
        with patch("rgpd.views.envoyer_email_accuse_rgpd", side_effect=RuntimeError("SMTP indisponible")):
            with self.assertLogs("comptes", level="ERROR"):
                response = self.client.post(reverse("rgpd:demande_rgpd_create"), {
                    "type": TypeDemande.ACCES,
                    "description": "Je souhaite accéder à mes données.",
                })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(DemandeRGPD.objects.filter(utilisateur=self.eleve).exists())

    def test_echec_reponse_rgpd_ne_bloque_pas_traitement(self):
        demande = self.creer_demande()
        self.client.force_login(self.admin_user)
        url = reverse("rgpd:admin_demande_rgpd_traiter", args=[demande.pk])
        with patch("rgpd.views.envoyer_email_reponse_rgpd", side_effect=RuntimeError("SMTP indisponible")):
            with self.assertLogs("comptes", level="ERROR"):
                response = self.client.post(url, {
                    "statut": StatutDemande.TRAITEE,
                    "motif_refus": "",
                })

        self.assertEqual(response.status_code, 302)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, StatutDemande.TRAITEE)
        self.assertTrue(demande.date_traitement)
