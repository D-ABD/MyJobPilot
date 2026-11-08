from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from core.gamification import (
    calculer_niveau,
    calculer_progression_utilisateur,
    calculer_xp,
    verifier_et_attribuer_badges,
)
from core.models import Badge, BadgeObtenu, Niveau
from entreprises.models import Entreprise, Prospection, Relance, Statut


class GamificationModelTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="badge-model-eleve", password="test", role=Utilisateur.Role.ELEVE
        )

    def test_relance_creation_et_str(self):
        prospection = Prospection.objects.create(
            eleve=self.eleve, entreprise=Entreprise.objects.create(nom="Relance modèle")
        )
        relance = Relance.objects.create(prospection=prospection, auteur=self.eleve)
        self.assertEqual(relance.type, Relance.Type.PROSPECTION)
        self.assertIn("Relance de prospection", str(relance))

    def test_badge_creation_et_str(self):
        badge = Badge.objects.create(
            slug="test-badge-model", categorie=Badge.Categorie.PROSPECTION,
            nom="Badge de test", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
        )
        self.assertEqual(str(badge), "Badge de test")

    def test_badge_obtenu_creation_et_str(self):
        badge = Badge.objects.create(
            slug="test-badge-obtenu", categorie=Badge.Categorie.SUIVI,
            nom="Relance test", type_condition=Badge.TypeCondition.RELANCES_COUNT,
        )
        obtenu = BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        self.assertIn("Relance test", str(obtenu))

    def test_badge_obtenu_est_unique_par_utilisateur_et_badge(self):
        badge = Badge.objects.create(
            slug="test-badge-unique", categorie=Badge.Categorie.PROSPECTION,
            nom="Unique", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
        )
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        # L'unicité est imposée par la base, indépendamment du service.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)

    def test_statut_terminee_est_disponible(self):
        self.assertIn(("terminee", "Terminée"), Statut.choices)


class AttributionBadgesTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="badge-eleve", password="test", role=Utilisateur.Role.ELEVE
        )

    def creer_prospection(self, index, statut):
        return Prospection.objects.create(
            eleve=self.eleve,
            entreprise=Entreprise.objects.create(nom=f"Badge entreprise {index}"),
            statut=statut,
        )

    def test_seuil_atteint_attribue_le_badge(self):
        badge = Badge.objects.create(
            slug="contactees-2-test", categorie=Badge.Categorie.PROSPECTION,
            nom="Deux démarches", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=2,
        )
        self.creer_prospection(1, Statut.REFUS)
        self.creer_prospection(2, Statut.ACCEPTE)
        verifier_et_attribuer_badges(self.eleve)
        self.assertTrue(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_seuil_non_atteint_ne_attribue_pas_le_badge(self):
        badge = Badge.objects.create(
            slug="contactees-3-test", categorie=Badge.Categorie.PROSPECTION,
            nom="Trois démarches", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=3,
        )
        self.creer_prospection(1, Statut.REFUS)
        verifier_et_attribuer_badges(self.eleve)
        self.assertFalse(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_attribution_est_idempotente(self):
        badge = Badge.objects.create(
            slug="contactees-1-idempotent", categorie=Badge.Categorie.PROSPECTION,
            nom="Une démarche", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=1,
        )
        self.creer_prospection(1, Statut.REFUS)
        verifier_et_attribuer_badges(self.eleve)
        verifier_et_attribuer_badges(self.eleve)
        self.assertEqual(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).count(), 1)

    def test_badge_inactif_n_est_pas_attribue(self):
        badge = Badge.objects.create(
            slug="badge-inactif-test", categorie=Badge.Categorie.PROSPECTION,
            nom="Inactif", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=1, est_actif=False,
        )
        self.creer_prospection(1, Statut.REFUS)
        verifier_et_attribuer_badges(self.eleve)
        self.assertFalse(BadgeObtenu.objects.filter(utilisateur=self.eleve, b