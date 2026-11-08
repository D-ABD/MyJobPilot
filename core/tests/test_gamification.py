from django.db import IntegrityError, transaction
from django.test import TestCase

from comptes.models import Utilisateur
from core.gamification import verifier_et_attribuer_badges
from core.models import Badge, BadgeObtenu
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
        self.assertFalse(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_badge_desactive_apres_obtention_reste_obtenu(self):
        badge = Badge.objects.create(
            slug="badge-desactive-apres-test", categorie=Badge.Categorie.PROSPECTION,
            nom="Conservé", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=1,
        )
        self.creer_prospection(1, Statut.REFUS)
        verifier_et_attribuer_badges(self.eleve)
        badge.est_actif = False
        badge.save(update_fields=["est_actif"])
        verifier_et_attribuer_badges(self.eleve)
        self.assertTrue(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_modifier_un_seuil_ne_retire_pas_un_badge_deja_obtenu(self):
        badge = Badge.objects.create(
            slug="badge-seuil-change-test", categorie=Badge.Categorie.PROSPECTION,
            nom="Seuil modifié", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=1,
        )
        self.creer_prospection(1, Statut.REFUS)
        verifier_et_attribuer_badges(self.eleve)
        badge.seuil = 100
        badge.save(update_fields=["seuil"])
        verifier_et_attribuer_badges(self.eleve)
        self.assertTrue(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_condition_prospections_compte_les_statuts_contactes(self):
        badge = Badge.objects.create(
            slug="contactees-type-test", categorie=Badge.Categorie.PROSPECTION,
            nom="Contacté", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=1,
        )
        self.creer_prospection(1, Statut.EN_ATTENTE)
        verifier_et_attribuer_badges(self.eleve)
        self.assertTrue(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_condition_candidatures_compte_les_statuts_de_candidature(self):
        badge = Badge.objects.create(
            slug="candidature-type-test", categorie=Badge.Categorie.CANDIDATURE,
            nom="Candidature", type_condition=Badge.TypeCondition.CANDIDATURES_COUNT,
            seuil=1,
        )
        self.creer_prospection(1, Statut.CANDIDATURE_ENVOYEE)
        verifier_et_attribuer_badges(self.eleve)
        self.assertTrue(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_condition_relances_compte_les_evenements_reels(self):
        badge = Badge.objects.create(
            slug="relance-type-test", categorie=Badge.Categorie.SUIVI,
            nom="Relance", type_condition=Badge.TypeCondition.RELANCES_COUNT,
            seuil=1,
        )
        prospection = self.creer_prospection(1, Statut.A_RELANCER)
        Relance.objects.create(prospection=prospection, auteur=self.eleve)
        verifier_et_attribuer_badges(self.eleve)
        self.assertTrue(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_statut_terminee_ne_compte_pas_dans_badges_prospection(self):
        badge = Badge.objects.create(
            slug="terminee-non-comptee-test", categorie=Badge.Categorie.PROSPECTION,
            nom="Démarche contactée", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil=1,
        )
        self.creer_prospection(1, Statut.TERMINEE)
        verifier_et_attribuer_badges(self.eleve)
        self.assertFalse(BadgeObtenu.objects.filter(utilisateur=self.eleve, badge=badge).exists())

    def test_verification_reste_a_trois_requetes_avec_17_et_50_badges(self):
        self.assertEqual(Badge.objects.count(), 17)
        for index in range(100):
            self.creer_prospection(index, Statut.REFUS)
        with self.assertNumQueries(3):
            verifier_et_attribuer_badges(self.eleve)
        for index in range(33):
            Badge.objects.create(
                slug=f"synthetique-{index}", categorie=Badge.Categorie.PROSPECTION,
                nom=f"Synthétique {index}",
                type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
                seuil=1,
            )
        self.assertEqual(Badge.objects.count(), 50)
        with self.assertNumQueries(3):
            verifier_et_attribuer_badges(self.eleve)


class BadgesPageTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="page-badges-eleve", password="test", role=Utilisateur.Role.ELEVE,
            is_valide=True,
        )

    def test_page_badges_non_connecte_redirige_vers_connexion(self):
        from django.urls import reverse

        response = self.client.get(reverse("core:mes_badges"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    def test_eleve_voit_ses_badges_et_ses_points(self):
        badge = Badge.objects.create(
            slug="page-badge-obtenu", categorie=Badge.Categorie.PROSPECTION,
            nom="Badge personnel", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            valeur_points=25,
        )
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        self.client.force_login(self.eleve)
        response = self.client.get("/mon-compte/badges/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Badge personnel")
        self.assertContains(response, "25 points")

    def test_page_badges_groupe_les_categories_et_affiche_la_progression(self):
        self.client.force_login(self.eleve)
        response = self.client.get("/mon-compte/badges/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prospection")
        self.assertContains(response, "Candidature")
        self.assertContains(response, "Suivi")
        self.assertContains(response, "Progression : 0/10")

    def test_superviseur_et_admin_ne_peuvent_pas_ouvrir_mon_compte_badges(self):
        from django.urls import reverse

        for role in (Utilisateur.Role.SUPERVISEUR, Utilisateur.Role.ADMIN):
            utilisateur = Utilisateur.objects.create_user(
                username=f"page-badges-{role}", password="test", role=role,
            )
            self.client.force_login(utilisateur)
            response = self.client.get(reverse("core:mes_badges"))
            self.assertEqual(response.status_code, 403)

    def test_dashboard_eleve_affiche_la_carte_points_badges(self):
        from django.urls import reverse

        self.client.force_login(self.eleve)
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Points : 0")
        self.assertContains(response, "Badges : 0/17")
        self.assertContains(response, reverse("core:mes_badges"))
