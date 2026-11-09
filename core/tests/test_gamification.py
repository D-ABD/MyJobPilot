from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from comptes.models import Notification, TypeNotification, Utilisateur
from core.gamification import (
    calculer_derniers_badges,
    calculer_niveau,
    calculer_prochain_badge,
    calculer_progression_categories,
    calculer_progression_utilisateur,
    calculer_xp,
    verifier_et_attribuer_badges,
    verifier_et_notifier_progression,
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
        with patch("comptes.notifications.creer_notification"):
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
        with patch("comptes.notifications.creer_notification"):
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


class CalculXPTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="xp-eleve", password="test", role=Utilisateur.Role.ELEVE,
            is_valide=True,
        )

    def creer_prospection(self, index, statut):
        return Prospection.objects.create(
            eleve=self.eleve,
            entreprise=Entreprise.objects.create(nom=f"Entreprise XP {index}"),
            statut=statut,
        )

    def test_calculer_xp_vide(self):
        self.assertEqual(calculer_xp(self.eleve), 0)

    def test_calculer_xp_prospections(self):
        for index in range(5):
            self.creer_prospection(index, Statut.A_RELANCER)
        self.assertEqual(calculer_xp(self.eleve), 50)

    def test_calculer_xp_candidatures(self):
        for index in range(3):
            self.creer_prospection(index, Statut.CANDIDATURE_ENVOYEE)
        # Chaque candidature figure aussi parmi les prospections contactées
        # selon la définition du lot (tous les statuts sauf A_CONTACTER/TERMINEE).
        self.assertEqual(calculer_xp(self.eleve), 90)

    def test_calculer_xp_relances(self):
        for index in range(2):
            prospection = self.creer_prospection(index, Statut.A_RELANCER)
            Relance.objects.create(prospection=prospection, auteur=self.eleve)
        # A_RELANCER apporte aussi 10 XP comme prospection contactée.
        self.assertEqual(calculer_xp(self.eleve), 40)

    def test_calculer_xp_complet_additionne_les_trois_familles(self):
        for index in range(2):
            self.creer_prospection(index, Statut.A_RELANCER)
        self.creer_prospection(2, Statut.CANDIDATURE_ENVOYEE)
        prospection = self.creer_prospection(3, Statut.A_RELANCER)
        Relance.objects.create(prospection=prospection, auteur=self.eleve)
        self.assertEqual(calculer_xp(self.eleve), 70)

    def test_calculer_xp_exclut_a_contacter(self):
        self.creer_prospection(1, Statut.A_CONTACTER)
        self.assertEqual(calculer_xp(self.eleve), 0)

    def test_calculer_xp_exclut_terminee(self):
        self.creer_prospection(1, Statut.TERMINEE)
        self.assertEqual(calculer_xp(self.eleve), 0)

    def test_calculer_xp_utilise_une_requete_par_source(self):
        with self.assertNumQueries(2):
            calculer_xp(self.eleve)


class CalculNiveauTests(TestCase):
    def test_calculer_niveau_novice(self):
        niveau = calculer_niveau(50)
        self.assertEqual(niveau["nom"], "Novice")
        self.assertEqual(niveau["xp_pour_suivant"], 50)
        self.assertEqual(niveau["niveau_suivant_nom"], "Explorateur")

    def test_calculer_niveau_explorateur(self):
        niveau = calculer_niveau(150)
        self.assertEqual(niveau["nom"], "Explorateur")
        self.assertEqual(niveau["xp_dans_niveau"], 50)
        self.assertEqual(niveau["xp_pour_suivant"], 100)

    def test_calculer_niveau_ambassadeur_est_le_niveau_maximal(self):
        niveau = calculer_niveau(5000)
        self.assertEqual(niveau["nom"], "Ambassadeur")
        self.assertTrue(niveau["est_max"])
        self.assertIsNone(niveau["xp_pour_suivant"])
        self.assertEqual(niveau["progression"], 1.0)

    def test_calculer_niveau_progression_intermediaire(self):
        niveau = calculer_niveau(175)
        self.assertEqual(niveau["progression"], 0.5)
        self.assertEqual(niveau["progression_pourcentage"], 50)

    def test_calculer_niveau_sans_niveaux_actifs_ne_plante_pas(self):
        Niveau.objects.update(est_actif=False)
        niveau = calculer_niveau(150)
        self.assertEqual(niveau["nom"], "—")
        self.assertEqual(niveau["xp_dans_niveau"], 150)

    def test_calculer_progression_utilisateur_retourne_le_resume_complet(self):
        prospection = Prospection.objects.create(
            eleve=self.eleve,
            entreprise=Entreprise.objects.create(nom="Entreprise résumé XP"),
            statut=Statut.CANDIDATURE_ENVOYEE,
        )
        Relance.objects.create(prospection=prospection, auteur=self.eleve)
        progression = calculer_progression_utilisateur(self.eleve)
        self.assertEqual(progression["xp"], 40)
        self.assertEqual(progression["niveau"]["nom"], "Novice")
        self.assertIn("points", progression)
        self.assertIn("badges_obtenus", progression)
        self.assertEqual(progression["badges_total"], Badge.objects.filter(est_actif=True).count())
        self.assertEqual(progression["compteurs_badges"]["candidatures"], 1)

    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="resume-xp-eleve", password="test", role=Utilisateur.Role.ELEVE,
            is_valide=True,
        )


class NiveauModelAndAdminTests(TestCase):
    def test_niveau_migration_cree_les_sept_paliers_initiaux(self):
        self.assertEqual(Niveau.objects.count(), 7)
        self.assertEqual(
            list(Niveau.objects.order_by("seuil_min").values_list("seuil_min", flat=True)),
            [0, 100, 250, 500, 1000, 2000, 4000],
        )

    def test_modifier_seuil_min_recalcule_le_niveau(self):
        niveau = Niveau.objects.get(nom="Explorateur")
        niveau.seuil_min = 120
        niveau.save(update_fields=["seuil_min"])
        self.assertEqual(calculer_niveau(110)["nom"], "Novice")
        self.assertEqual(calculer_niveau(120)["nom"], "Explorateur")

    def test_desactiver_un_niveau_le_retire_du_calcul(self):
        Niveau.objects.filter(nom="Persévérant").update(est_actif=False)
        self.assertEqual(calculer_niveau(300)["nom"], "Explorateur")

    def test_niveau_impose_l_unicite_du_nom_et_du_seuil(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Niveau.objects.create(nom="Autre Novice", seuil_min=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Niveau.objects.create(nom="Novice", seuil_min=9000)

    def test_admin_peut_creer_un_niveau_personnalise(self):
        admin = Utilisateur.objects.create_superuser(
            username="xp-admin", email="xp-admin@example.test", password="test",
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin:core_niveau_add"),
            {"nom": "Légende", "seuil_min": 8000, "ordre_affichage": 8, "est_actif": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(calculer_niveau(8500)["nom"], "Légende")


class XPTemplatesTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="xp-template-eleve", password="test", role=Utilisateur.Role.ELEVE,
            is_valide=True,
        )
        self.client.force_login(self.eleve)

    def test_dashboard_eleve_affiche_niveau_et_xp(self):
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Niveau : Novice")
        self.assertContains(response, "0 XP")
        self.assertContains(response, "Progression vers le niveau suivant")

    def test_page_badges_affiche_niveau_et_xp(self):
        response = self.client.get(reverse("core:mes_badges"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Niveau : Novice")
        self.assertContains(response, "0 XP")
        self.assertContains(response, "Progression vers le niveau suivant")


class ProgressionBadgesCategoriesTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="categories-badges-eleve", password="test",
            role=Utilisateur.Role.ELEVE, is_valide=True,
        )
        self.compteurs = {
            "prospections_contactees": 0,
            "candidatures": 0,
            "relances": 0,
        }

    def test_calculer_prochain_badge_progression_simple(self):
        badge = Badge.objects.get(slug="prospection-35")
        compteurs = {**self.compteurs, "prospections_contactees": 25}

        resultat = calculer_prochain_badge(
            self.eleve, Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            compteurs=compteurs,
        )

        self.assertEqual(resultat["prochain_badge"], badge)
        self.assertEqual(resultat["manque"], 10)
        self.assertEqual(resultat["progression"], 25 / 35)

    def test_calculer_prochain_badge_candidature(self):
        resultat = calculer_prochain_badge(
            self.eleve, Badge.TypeCondition.CANDIDATURES_COUNT,
            compteurs=self.compteurs,
        )
        self.assertEqual(resultat["prochain_badge"].slug, "candidature-3")
        self.assertEqual(resultat["seuil_cible"], 3)

    def test_calculer_prochain_badge_relance(self):
        resultat = calculer_prochain_badge(
            self.eleve, Badge.TypeCondition.RELANCES_COUNT,
            compteurs=self.compteurs,
        )
        self.assertEqual(resultat["prochain_badge"].slug, "relance-1")
        self.assertEqual(resultat["seuil_cible"], 1)

    def test_calculer_prochain_badge_ignore_les_badges_deja_obtenus(self):
        badges = list(Badge.objects.filter(
            type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            seuil__in=(10, 20),
        ))
        BadgeObtenu.objects.bulk_create([
            BadgeObtenu(utilisateur=self.eleve, badge=badge) for badge in badges
        ])
        compteurs = {**self.compteurs, "prospections_contactees": 22}

        resultat = calculer_prochain_badge(
            self.eleve, Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            compteurs=compteurs,
        )

        self.assertEqual(resultat["prochain_badge"].slug, "prospection-35")

    def test_calculer_prochain_badge_tous_obtenus(self):
        badges = list(Badge.objects.filter(
            est_actif=True,
            type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
        ))
        BadgeObtenu.objects.bulk_create([
            BadgeObtenu(utilisateur=self.eleve, badge=badge) for badge in badges
        ])
        compteurs = {**self.compteurs, "prospections_contactees": 150}

        resultat = calculer_prochain_badge(
            self.eleve, Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            compteurs=compteurs,
        )

        self.assertIsNone(resultat["prochain_badge"])
        self.assertTrue(resultat["tous_obtenus"])
        self.assertEqual(resultat["progression"], 1.0)

    def test_calculer_prochain_badge_aucun_badge_actif(self):
        Badge.objects.filter(
            type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
        ).update(est_actif=False)

        resultat = calculer_prochain_badge(
            self.eleve, Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            compteurs=self.compteurs,
        )

        self.assertIsNone(resultat["prochain_badge"])
        self.assertTrue(resultat["tous_obtenus"])

    def test_calculer_prochain_badge_requete_badges_active_independante_du_nombre(self):
        with patch("core.gamification.compter_progression", return_value=self.compteurs):
            with self.assertNumQueries(2):
                resultat = calculer_prochain_badge(
                    self.eleve, Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
                    compteurs=self.compteurs,
                )
                str(resultat["prochain_badge"])

    def test_calculer_prochain_badge_requete_badges_obtenus_unique(self):
        with patch("core.gamification.compter_progression", return_value=self.compteurs):
            with self.assertNumQueries(2):
                calculer_prochain_badge(
                    self.eleve, Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
                    compteurs=self.compteurs,
                )

    def test_calculer_progression_categories_retourne_les_trois_familles(self):
        with patch("core.gamification.compter_progression", return_value=self.compteurs) as compter:
            progression = calculer_progression_categories(self.eleve)

        compter.assert_called_once_with(self.eleve)
        self.assertEqual(set(progression), {"prospections", "candidatures", "relances"})
        self.assertEqual(progression["prospections"]["compteur_actuel"], 0)

    def test_calculer_derniers_badges_limite_a_cinq(self):
        badges = [
            Badge.objects.create(
                slug=f"dernier-badge-limite-{index}",
                categorie=Badge.Categorie.PROSPECTION,
                nom=f"Dernier badge {index}",
                type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
            )
            for index in range(10)
        ]
        BadgeObtenu.objects.bulk_create([
            BadgeObtenu(utilisateur=self.eleve, badge=badge) for badge in badges
        ])
        self.assertEqual(len(calculer_derniers_badges(self.eleve, 5)), 5)

    def test_calculer_derniers_badges_ordre_decroissant(self):
        anciens = Badge.objects.create(
            slug="dernier-badge-ancien", categorie=Badge.Categorie.PROSPECTION,
            nom="Badge ancien", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
        )
        recents = Badge.objects.create(
            slug="dernier-badge-recent", categorie=Badge.Categorie.PROSPECTION,
            nom="Badge récent", type_condition=Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT,
        )
        ancien = BadgeObtenu.objects.create(utilisateur=self.eleve, badge=anciens)
        recent = BadgeObtenu.objects.create(utilisateur=self.eleve, badge=recents)
        BadgeObtenu.objects.filter(pk=ancien.pk).update(date_obtention="2020-01-01T00:00:00Z")
        BadgeObtenu.objects.filter(pk=recent.pk).update(date_obtention="2025-01-01T00:00:00Z")

        resultat = calculer_derniers_badges(self.eleve)

        self.assertEqual(resultat[0].badge, recents)
        self.assertEqual(resultat[1].badge, anciens)

    def test_calculer_derniers_badges_charge_en_une_requete(self):
        badge = Badge.objects.create(
            slug="dernier-badge-une-requete", categorie=Badge.Categorie.SUIVI,
            nom="Badge joint", type_condition=Badge.TypeCondition.RELANCES_COUNT,
        )
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)

        with self.assertNumQueries(1):
            resultats = calculer_derniers_badges(self.eleve)
            noms = [attribution.badge.nom for attribution in resultats]

        self.assertEqual(noms, ["Badge joint"])

    def test_calculer_derniers_badges_garde_badge_desactive(self):
        badge = Badge.objects.create(
            slug="dernier-badge-desactive", categorie=Badge.Categorie.SUIVI,
            nom="Badge archivé", type_condition=Badge.TypeCondition.RELANCES_COUNT,
            est_actif=False,
        )
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        self.assertEqual(calculer_derniers_badges(self.eleve)[0].badge, badge)


class GamificationNotificationsTests(TestCase):
    def setUp(self):
        self.eleve = Utilisateur.objects.create_user(
            username="notifications-gamification-eleve", password="test",
            role=Utilisateur.Role.ELEVE, is_valide=True,
        )

    def _badge(self, slug, type_condition, seuil=1):
        return Badge.objects.create(
            slug=slug,
            categorie=(
                Badge.Categorie.PROSPECTION
                if type_condition == Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT
                else Badge.Categorie.CANDIDATURE
                if type_condition == Badge.TypeCondition.CANDIDATURES_COUNT
                else Badge.Categorie.SUIVI
            ),
            nom=f"Badge {slug}",
            type_condition=type_condition,
            seuil=seuil,
        )

    def _progressions(self, **overrides):
        return {
            categorie: {
                "prochain_badge": overrides.get(categorie),
                "manque": 0 if categorie not in overrides else overrides.get(f"{categorie}_manque", 1),
                "tous_obtenus": categorie not in overrides,
            }
            for categorie in ("prospections", "candidatures", "relances")
        }

    def test_verifier_et_attribuer_badges_cree_notification_badge_obtenu(self):
        badge = Badge.objects.get(slug="prospection-10")
        Badge.objects.exclude(pk=badge.pk).update(est_actif=False)
        for index in range(10):
            Prospection.objects.create(
                eleve=self.eleve,
                entreprise=Entreprise.objects.create(nom=f"Notification badge {index}"),
                statut=Statut.A_RELANCER,
            )

        verifier_et_attribuer_badges(self.eleve)

        notification = Notification.objects.get(destinataire=self.eleve)
        self.assertEqual(notification.type, TypeNotification.BADGE_OBTENU)
        self.assertEqual(notification.message, f"🏆 Badge débloqué : {badge.nom}")

    def test_verifier_et_attribuer_badges_pas_de_notification_si_deja_obtenu(self):
        badge = Badge.objects.get(slug="prospection-10")
        Badge.objects.exclude(pk=badge.pk).update(est_actif=False)
        BadgeObtenu.objects.create(utilisateur=self.eleve, badge=badge)
        for index in range(10):
            Prospection.objects.create(
                eleve=self.eleve,
                entreprise=Entreprise.objects.create(nom=f"Badge déjà obtenu {index}"),
                statut=Statut.A_RELANCER,
            )

        verifier_et_attribuer_badges(self.eleve)

        self.assertFalse(Notification.objects.exists())

    def test_verifier_et_attribuer_badges_notification_lien_contient_slug(self):
        badge = Badge.objects.get(slug="prospection-10")
        Badge.objects.exclude(pk=badge.pk).update(est_actif=False)
        for index in range(10):
            Prospection.objects.create(
                eleve=self.eleve,
                entreprise=Entreprise.objects.create(nom=f"Slug notification {index}"),
                statut=Statut.A_RELANCER,
            )

        verifier_et_attribuer_badges(self.eleve)

        self.assertEqual(
            Notification.objects.get(destinataire=self.eleve).lien,
            "/mon-compte/badges/#badge-prospection-10",
        )

    def test_verifier_et_notifier_progression_envoie_si_manque_5(self):
        badge = self._badge(
            "progression-exactement-cinq", Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT
        )
        with patch("core.gamification.calculer_progression_categories", return_value=self._progressions(
            prospections=badge, prospections_manque=5,
        )):
            notifications = verifier_et_notifier_progression(self.eleve)
        self.assertEqual(len(notifications), 1)
        self.assertIn("Plus que 5", notifications[0].message)

    def test_verifier_et_notifier_progression_envoie_si_manque_moins_5(self):
        badge = self._badge(
            "progression-trois-restants", Badge.TypeCondition.CANDIDATURES_COUNT
        )
        with patch("core.gamification.calculer_progression_categories", return_value=self._progressions(
            candidatures=badge, candidatures_manque=3,
        )):
            notifications = verifier_et_notifier_progression(self.eleve)
        self.assertEqual(len(notifications), 1)
        self.assertIn("Plus que 3", notifications[0].message)

    def test_verifier_et_notifier_progression_pas_si_manque_plus_5(self):
        badge = self._badge(
            "progression-six-restants", Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT
        )
        with patch("core.gamification.calculer_progression_categories", return_value=self._progressions(
            prospections=badge, prospections_manque=6,
        )):
            notifications = verifier_et_notifier_progression(self.eleve)
        self.assertEqual(notifications, [])
        self.assertFalse(Notification.objects.exists())

    def test_verifier_et_notifier_progression_pas_si_deja_envoyee(self):
        badge = self._badge(
            "progression-deja-envoyee", Badge.TypeCondition.PROSPECTIONS_CONTACTEES_COUNT
        )
        lien = f"/mon-compte/badges/#badge-{badge.slug}"
        Notification.objects.create(
            destinataire=self.eleve,
            type=TypeNotification.PROGRESSION_BADGE,
            message="Déjà notifiée",
            lien=lien,
        )
        with patch("core.gamification.calculer_progression_categories", return_value=self._progressions(
            prospections=badge, prospections_manque=2,
        )):
            notifications = verifier_et_notifier_progression(self.eleve)
        self.assertEqual(notifications, [])
        self.assertEqual(Notification.objects.filter(lien=lien).count(), 1)

    def test_verifier_et_notifier_progression_pas_si_tous_obtenus(self):
        with patch("core.gamification.calculer_progression_categories", return_value={
            categorie: {"prochain_badge": None, "manque": 0, "tous_obtenus": True}
            for categorie in ("prospections", "candidatures", "relances")
        }):
            notifications = verifier_et_notifier_progression(self.eleve)
        self.assertEqual(notifications, [])
        self.assertFalse(Notification.objects.exists())

    def test_verifier_et_notifier_progression_requetes_bornees(self):
        for index in range(5):
            Prospection.objects.create(
                eleve=self.eleve,
                entreprise=Entreprise.objects.create(nom=f"Fenêtre de progression {index}"),
                statut=Statut.A_RELANCER,
            )

        with self.assertNumQueries(12):
            notifications = verifier_et_notifier_progression(self.eleve)

        self.assertEqual(len(notifications), 3)
        self.assertEqual(
            Notification.objects.filter(
                destinataire=self.eleve, type=TypeNotification.PROGRESSION_BADGE,
            ).count(),
            3,
        )

    def test_mes_badges_cree_notifications_progression(self):
        for index in range(5):
            Prospection.objects.create(
                eleve=self.eleve,
                entreprise=Entreprise.objects.create(nom=f"Page badges progression {index}"),
                statut=Statut.A_RELANCER,
            )
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("core:mes_badges"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(
                destinataire=self.eleve, type=TypeNotification.PROGRESSION_BADGE,
            ).count(),
            3,
        )
        self.assertContains(response, 'id="badge-prospection-10"')
