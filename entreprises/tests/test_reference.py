"""Tests d'isolation et de filtres du référentiel des entreprises."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, ScopeSuperviseur, Utilisateur
from entreprises.models import Entreprise, Prospection


class EntreprisesReferenceTests(TestCase):
    def setUp(self):
        self.centre_paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation_paris, _ = Formation.objects.get_or_create(
            centre=self.centre_paris,
            nom="BTS Référentiel Lot 10",
        )
        self.centre_lyon, _ = Centre.objects.get_or_create(
            nom="Centre Lot 10 Lyon",
            defaults={"departement": "69 - Rhône"},
        )
        self.formation_lyon, _ = Formation.objects.get_or_create(
            centre=self.centre_lyon,
            nom="BTS Référentiel Lot 10 Lyon",
        )
        self.eleve = self.creer_utilisateur(
            "eleve_ref_10", Utilisateur.Role.ELEVE, self.centre_paris, self.formation_paris,
        )
        self.autre_eleve = self.creer_utilisateur(
            "autre_eleve_ref_10", Utilisateur.Role.ELEVE, self.centre_paris, self.formation_paris,
        )
        self.eleve_hors_scope = self.creer_utilisateur(
            "eleve_hors_ref_10", Utilisateur.Role.ELEVE, self.centre_lyon, self.formation_lyon,
        )
        self.superviseur = self.creer_utilisateur(
            "superviseur_ref_10", Utilisateur.Role.SUPERVISEUR, self.centre_paris,
        )
        self.autre_superviseur = self.creer_utilisateur(
            "autre_superviseur_ref_10", Utilisateur.Role.SUPERVISEUR, self.centre_lyon,
        )
        self.admin = self.creer_utilisateur("admin_ref_10", Utilisateur.Role.ADMIN)
        ScopeSuperviseur.objects.create(
            superviseur=self.superviseur,
            centre=self.centre_paris,
            is_active=True,
        )

    def creer_utilisateur(self, username, role, centre=None, formation=None):
        return Utilisateur.objects.create_user(
            username=username,
            password="MotDePasseLot10!",
            role=role,
            centre=centre,
            formation=formation,
            is_valide=True,
        )

    def creer_prospection(self, proprietaire, nom, **entreprise_data):
        entreprise = Entreprise.objects.create(nom=nom, **entreprise_data)
        Prospection.objects.create(eleve=proprietaire, entreprise=entreprise)
        return entreprise

    def test_eleve_voit_uniquement_ses_entreprises(self):
        visible = self.creer_prospection(self.eleve, "Visible élève")
        self.creer_prospection(self.autre_eleve, "Privée autre élève")
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:reference"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["entreprises"]), [visible])
        self.assertNotContains(response, reverse("entreprises:reference_create"))
        self.assertNotContains(response, "Modifier")
        self.assertNotContains(response, "Supprimer")

    def test_superviseur_voit_scope_et_ses_entreprises(self):
        propre = self.creer_prospection(self.superviseur, "Entreprise superviseur")
        dans_scope = self.creer_prospection(self.eleve, "Entreprise scope")
        self.creer_prospection(self.eleve_hors_scope, "Entreprise hors scope")
        self.creer_prospection(self.autre_superviseur, "Entreprise autre superviseur")
        self.client.force_login(self.superviseur)

        response = self.client.get(reverse("entreprises:reference"))

        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(response.context["entreprises"]), {propre, dans_scope})

    def test_admin_voit_tout(self):
        entreprises = {
            self.creer_prospection(self.eleve, "Référentiel admin élève"),
            self.creer_prospection(self.eleve_hors_scope, "Référentiel admin hors scope"),
            self.creer_prospection(self.superviseur, "Référentiel admin superviseur"),
            Entreprise.objects.create(nom="Référentiel admin sans prospection"),
        }
        self.client.force_login(self.admin)

        response = self.client.get(reverse("entreprises:reference"))

        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(response.context["entreprises"]), entreprises)
        self.assertContains(response, reverse("entreprises:reference_create"))
        self.assertContains(response, reverse("entreprises:reference_update", args=[next(iter(entreprises)).pk]))

    def test_filtre_q_est_insensible_aux_accents_et_a_la_casse(self):
        visible = self.creer_prospection(
            self.eleve, "École Étoile",
            secteur="Éducation",
            ville="Évry",
        )
        self.creer_prospection(self.eleve, "Autre entreprise", secteur="Commerce", ville="Lyon")
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:reference"), {"q": "ecole etoile"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["entreprises"]), [visible])

    def test_filtre_secteur(self):
        visible = self.creer_prospection(self.eleve, "Entreprise secteur A", secteur="Santé")
        self.creer_prospection(self.eleve, "Entreprise secteur B", secteur="Commerce")
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:reference"), {"secteur": "Santé"})

        self.assertEqual(list(response.context["entreprises"]), [visible])

    def test_filtre_ville(self):
        visible = self.creer_prospection(self.eleve, "Entreprise ville A", ville="Paris")
        self.creer_prospection(self.eleve, "Entreprise ville B", ville="Lyon")
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:reference"), {"ville": "Paris"})

        self.assertEqual(list(response.context["entreprises"]), [visible])

    def test_pagination_et_persistance_des_filtres_et_du_tri(self):
        for index in range(26):
            self.creer_prospection(
                self.eleve, f"Entreprise pagination {index:02}", secteur="Tech", ville="Paris",
            )
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:reference"), {
            "q": "pagination", "secteur": "Tech", "ville": "Paris",
            "tri": "nom", "ordre": "asc", "page": "2",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertIn("q=pagination", response.context["pagination_query"])
        self.assertIn("secteur=Tech", response.context["pagination_query"])
        self.assertIn("tri=nom", response.context["pagination_query"])
        self.assertIn("ordre=asc", response.context["pagination_query"])
        self.assertNotIn("page=2", response.context["pagination_query"])
        self.assertIn("tri=ville", response.context["tri_urls"]["ville"])
        self.assertIn("secteur=Tech", response.context["tri_urls"]["ville"])

    def test_detail_entreprise_isolation_eleve(self):
        entreprise_visible = self.creer_prospection(self.eleve, "Détail visible élève")
        entreprise_privee = self.creer_prospection(self.autre_eleve, "Détail privé élève")
        self.client.force_login(self.eleve)

        response_visible = self.client.get(reverse(
            "entreprises:reference_detail", kwargs={"pk": entreprise_visible.pk},
        ))
        response_privee = self.client.get(reverse(
            "entreprises:reference_detail", kwargs={"pk": entreprise_privee.pk},
        ))

        self.assertEqual(response_visible.status_code, 200)
        self.assertEqual(list(response_visible.context["prospections"]), list(
            Prospection.objects.filter(eleve=self.eleve, entreprise=entreprise_visible),
        ))
        self.assertEqual(response_privee.status_code, 404)

    def test_detail_entreprise_isolation_superviseur(self):
        entreprise_scope = self.creer_prospection(self.eleve, "Détail scope superviseur")
        entreprise_hors_scope = self.creer_prospection(self.eleve_hors_scope, "Détail hors scope superviseur")
        self.client.force_login(self.superviseur)

        response_scope = self.client.get(reverse(
            "entreprises:reference_detail", kwargs={"pk": entreprise_scope.pk},
        ))
        response_hors_scope = self.client.get(reverse(
            "entreprises:reference_detail", kwargs={"pk": entreprise_hors_scope.pk},
        ))

        self.assertEqual(response_scope.status_code, 200)
        self.assertEqual(response_hors_scope.status_code, 404)

    def test_non_authentifie_403(self):
        response = self.client.get(reverse("entreprises:reference"))
        self.assertEqual(response.status_code, 403)

    def test_admin_peut_creer_entreprise(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("entreprises:reference_create"),
            {"nom": "Nouvelle entreprise admin", "secteur": "Tech", "ville": "Paris"},
        )

        self.assertRedirects(response, reverse("entreprises:reference"))
        self.assertTrue(Entreprise.objects.filter(nom="Nouvelle entreprise admin").exists())

    def test_admin_peut_modifier_entreprise(self):
        entreprise = Entreprise.objects.create(nom="Entreprise à modifier")
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("entreprises:reference_update", args=[entreprise.pk]),
            {"nom": "Entreprise modifiée", "secteur": "Conseil", "ville": "Lyon"},
        )

        self.assertRedirects(response, reverse("entreprises:reference"))
        entreprise.refresh_from_db()
        self.assertEqual(entreprise.nom, "Entreprise modifiée")
        self.assertEqual(entreprise.secteur, "Conseil")
        self.assertEqual(entreprise.ville, "Lyon")

    def test_admin_peut_supprimer_entreprise_sans_prospection(self):
        entreprise = Entreprise.objects.create(nom="Entreprise supprimable")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("entreprises:reference_delete", args=[entreprise.pk]))

        self.assertRedirects(response, reverse("entreprises:reference"))
        self.assertFalse(Entreprise.objects.filter(pk=entreprise.pk).exists())

    def test_admin_ne_peut_pas_supprimer_entreprise_avec_prospection(self):
        entreprise = self.creer_prospection(self.eleve, "Entreprise protégée")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("entreprises:reference_delete", args=[entreprise.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ne peut pas être supprimée")
        self.assertContains(response, "1 prospection y est encore liée.")
        self.assertTrue(Entreprise.objects.filter(pk=entreprise.pk).exists())
        self.assertTrue(Prospection.objects.filter(entreprise=entreprise).exists())

    def test_eleve_ne_peut_pas_creer_entreprise(self):
        self.client.force_login(self.eleve)

        response = self.client.post(
            reverse("entreprises:reference_create"),
            {"nom": "Entreprise interdite élève"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Entreprise.objects.filter(nom="Entreprise interdite élève").exists())

    def test_superviseur_ne_peut_pas_creer_entreprise(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(
            reverse("entreprises:reference_create"),
            {"nom": "Entreprise interdite superviseur"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Entreprise.objects.filter(nom="Entreprise interdite superviseur").exists())

    def test_non_admin_ne_peut_pas_modifier_ou_supprimer_entreprise(self):
        entreprise = self.creer_prospection(self.eleve, "Entreprise gestion protégée")
        for utilisateur in (self.eleve, self.superviseur):
            with self.subTest(role=utilisateur.role):
                self.client.force_login(utilisateur)
                response_modifier = self.client.get(
                    reverse("entreprises:reference_update", args=[entreprise.pk]),
                )
                response_supprimer = self.client.post(
                    reverse("entreprises:reference_delete", args=[entreprise.pk]),
                )
                self.assertEqual(response_modifier.status_code, 403)
                self.assertEqual(response_supprimer.status_code, 403)
        self.assertTrue(Entreprise.objects.filter(pk=entreprise.pk).exists())
