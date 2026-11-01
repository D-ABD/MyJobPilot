"""Tests des dashboards et de l'isolation du périmètre staff."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, ScopeSuperviseur, Utilisateur
from entreprises.models import Entreprise, Prospection, Statut


class VuesStaffTests(TestCase):
    def setUp(self):
        self.centre_a = Centre.objects.create(nom="Centre staff vues A", departement="75 - Paris")
        self.centre_b = Centre.objects.create(nom="Centre staff vues B", departement="69 - Rhône")
        self.formation_a = Formation.objects.create(centre=self.centre_a, nom="Formation staff A")
        self.formation_b = Formation.objects.create(centre=self.centre_b, nom="Formation staff B")
        self.superviseur = self.creer_superviseur()
        self.eleve_a = self.creer_eleve("alice", "Martin", self.centre_a, self.formation_a)
        self.eleve_b = self.creer_eleve("bob", "Durand", self.centre_b, self.formation_b)

    def creer_superviseur(self):
        return Utilisateur.objects.create_user(
            username="superviseur_staff",
            password=None,
            role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre_a,
            is_staff=True,
            is_valide=True,
        )

    def creer_eleve(self, username, nom, centre, formation, is_valide=True):
        return Utilisateur.objects.create_user(
            username=username,
            password=None,
            first_name="Prénom",
            last_name=nom,
            email=f"{username}@example.com",
            role=Utilisateur.Role.ELEVE,
            centre=centre,
            formation=formation,
            is_valide=is_valide,
        )

    def ajouter_scope(self, centre=None):
        return ScopeSuperviseur.objects.create(
            superviseur=self.superviseur,
            centre=centre or self.centre_a,
        )

    def connecter(self, utilisateur=None):
        self.client.force_login(utilisateur or self.superviseur)

    def test_dashboard_sans_authentification_redirige_vers_connexion(self):
        response = self.client.get(reverse("staff:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    def test_dashboard_refuse_un_eleve(self):
        self.connecter(self.eleve_a)
        response = self.client.get(reverse("staff:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_refuse_un_administrateur(self):
        administrateur = Utilisateur.objects.create_superuser(
            username="admin_staff", email="admin@example.com", password="mot-de-passe"
        )
        self.connecter(administrateur)
        response = self.client.get(reverse("staff:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_superviseur_sans_scope_est_vide(self):
        self.connecter()
        response = self.client.get(reverse("staff:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 0)
        self.assertContains(response, "Aucun élève dans votre périmètre.")

    def test_dashboard_affiche_uniquement_les_eleves_dans_le_scope(self):
        self.ajouter_scope()
        self.connecter()
        response = self.client.get(reverse("staff:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alice")
        self.assertNotContains(response, "bob")
        self.assertEqual(list(response.context["eleves"]), [self.eleve_a])

    def test_dashboard_recherche_filtre_les_eleves(self):
        self.ajouter_scope()
        self.connecter()
        response = self.client.get(reverse("staff:dashboard"), {"q": "martin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(list(response.context["eleves"]), [self.eleve_a])

    def test_dashboard_filtre_par_centre_dans_le_scope(self):
        self.ajouter_scope(self.centre_a)
        self.ajouter_scope(self.centre_b)
        self.connecter()
        response = self.client.get(reverse("staff:dashboard"), {"centre": str(self.centre_b.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["eleves"]), [self.eleve_b])

    def test_dashboard_ne_permet_pas_de_filtrer_sur_un_centre_hors_scope(self):
        self.ajouter_scope(self.centre_a)
        self.connecter()
        response = self.client.get(reverse("staff:dashboard"), {"centre": str(self.centre_b.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 0)

    def test_dashboard_filtre_par_etat_de_validation(self):
        self.ajouter_scope()
        self.creer_eleve("attente", "En attente", self.centre_a, self.formation_a, is_valide=False)
        self.connecter()
        response = self.client.get(reverse("staff:dashboard"), {"is_valide": "false"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([eleve.username for eleve in response.context["eleves"]], ["attente"])

    def test_dashboard_trie_par_colonne_et_conserve_les_filtres(self):
        self.ajouter_scope()
        self.creer_eleve("charlie", "Zulu", self.centre_a, self.formation_a)
        self.connecter()
        response = self.client.get(
            reverse("staff:dashboard"),
            {"tri": "last_name", "ordre": "desc", "q": ""},
        )
        self.assertEqual(
            [eleve.last_name for eleve in response.context["eleves"]],
            ["Zulu", "Martin"],
        )
        self.assertIn("tri=username", response.context["tri_urls"]["username"])
        self.assertIn("ordre=asc", response.context["tri_urls"]["username"])

    def test_dashboard_pagine_vingt_cinq_eleves(self):
        self.ajouter_scope()
        for numero in range(26):
            self.creer_eleve(f"eleve{numero:02d}", f"Nom{numero:02d}", self.centre_a, self.formation_a)
        self.connecter()
        response = self.client.get(reverse("staff:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["eleves"]), 25)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)

    def test_detail_eleve_dans_le_scope_est_visible(self):
        self.ajouter_scope()
        self.connecter()
        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["eleve"], self.eleve_a)

    def test_detail_eleve_hors_scope_est_refuse(self):
        self.ajouter_scope()
        self.connecter()
        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve_b.pk]))
        self.assertEqual(response.status_code, 403)

    def test_detail_eleve_refuse_un_eleve_connecte(self):
        self.connecter(self.eleve_a)
        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve_a.pk]))
        self.assertEqual(response.status_code, 403)

    def test_detail_eleve_autorise_un_admin(self):
        administrateur = Utilisateur.objects.create_superuser(
            username="admin_detail_staff", email="detail@example.com", password="mot-de-passe"
        )
        self.connecter(administrateur)
        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve_a.pk]))
        self.assertEqual(response.status_code, 200)

    def test_detail_eleve_affiche_prospections_sans_actions(self):
        self.ajouter_scope()
        entreprise = Entreprise.objects.create(nom="Entreprise visible")
        Prospection.objects.create(eleve=self.eleve_a, entreprise=entreprise, statut=Statut.A_RELANCER)
        self.connecter()
        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entreprise visible")
        self.assertContains(response, "À relancer")
        self.assertNotContains(response, "Modifier")
        self.assertNotContains(response, "Supprimer")

    def test_redirection_apres_login_superviseur_vers_staff(self):
        self.connecter()
        response = self.client.get(reverse("comptes:redirection_apres_login"))
        self.assertRedirects(response, reverse("staff:dashboard"))
