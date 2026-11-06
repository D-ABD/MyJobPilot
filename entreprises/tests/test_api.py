"""Tests de l'API JSON des prospections et de ses périmètres."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, ScopeSuperviseur, Utilisateur
from entreprises.models import Entreprise, Prospection, Statut, TypeContrat


class ProspectionsApiTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(
            centre=self.centre,
            nom="BTS SIO",
        )
        self.autre_centre, _ = Centre.objects.get_or_create(
            nom="Centre API autre",
            defaults={"departement": "69 - Rhône"},
        )
        self.autre_formation, _ = Formation.objects.get_or_create(
            centre=self.autre_centre,
            nom="BUT API",
        )
        self.eleve = self.creer_utilisateur(
            "api_eleve", Utilisateur.Role.ELEVE, self.centre, self.formation
        )
        self.autre_eleve = self.creer_utilisateur(
            "api_autre_eleve", Utilisateur.Role.ELEVE,
            self.autre_centre, self.autre_formation,
        )
        self.superviseur = self.creer_utilisateur(
            "api_superviseur", Utilisateur.Role.SUPERVISEUR
        )
        self.autre_superviseur = self.creer_utilisateur(
            "api_autre_superviseur", Utilisateur.Role.SUPERVISEUR
        )
        self.admin = self.creer_utilisateur("api_admin", Utilisateur.Role.ADMIN)
        ScopeSuperviseur.objects.create(
            superviseur=self.superviseur, centre=self.centre, is_active=True
        )
        self.prospection_eleve = self.creer_prospection(self.eleve, "API élève")
        self.prospection_autre_eleve = self.creer_prospection(
            self.autre_eleve, "API autre élève"
        )
        self.prospection_superviseur = self.creer_prospection(
            self.superviseur, "API superviseur"
        )
        self.prospection_autre_superviseur = self.creer_prospection(
            self.autre_superviseur, "API autre superviseur"
        )
        self.prospection_admin = self.creer_prospection(self.admin, "API admin")
        self.url = reverse("api_prospections")

    @staticmethod
    def creer_utilisateur(username, role, centre=None, formation=None):
        return Utilisateur.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="MotDePasse2026!",
            role=role,
            centre=centre,
            formation=formation,
            is_valide=True,
        )

    @staticmethod
    def creer_prospection(eleve, nom):
        entreprise = Entreprise.objects.create(nom=nom, ville="Paris")
        return Prospection.objects.create(
            eleve=eleve,
            entreprise=entreprise,
            statut=Statut.A_CONTACTER,
            type_contrat=TypeContrat.ALTERNANCE,
        )

    def test_reponse_contient_le_schema_json_attendu(self):
        self.client.force_login(self.eleve)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        objet = response.json()[0]
        self.assertEqual(
            set(objet),
            {
                "id", "entreprise", "statut", "statut_display",
                "type_contrat", "type_contrat_display",
                "date_creation", "date_modification",
            },
        )
        self.assertEqual(set(objet["entreprise"]), {"id", "nom", "ville"})
        self.assertEqual(objet["statut"], "a_contacter")
        self.assertEqual(objet["statut_display"], "À contacter")
        self.assertEqual(objet["type_contrat"], "alternance")
        self.assertEqual(objet["type_contrat_display"], "Alternance")
        self.assertTrue(objet["date_creation"])
        self.assertTrue(objet["date_modification"])

    def test_eleve_ne_voit_que_ses_prospections(self):
        self.client.force_login(self.eleve)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x["id"] for x in response.json()], [self.prospection_eleve.pk])

    def test_superviseur_voit_ses_prospections_et_son_scope(self):
        self.client.force_login(self.superviseur)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ids = {x["id"] for x in response.json()}
        self.assertEqual(ids, {self.prospection_eleve.pk, self.prospection_superviseur.pk})
        self.assertNotIn(self.prospection_autre_eleve.pk, ids)
        self.assertNotIn(self.prospection_autre_superviseur.pk, ids)

    def test_admin_voit_toutes_les_prospections(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {x["id"] for x in response.json()},
            {
                self.prospection_eleve.pk,
                self.prospection_autre_eleve.pk,
                self.prospection_superviseur.pk,
                self.prospection_autre_superviseur.pk,
                self.prospection_admin.pk,
            },
        )

    def test_utilisateur_non_authentifie_est_refuse(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))
