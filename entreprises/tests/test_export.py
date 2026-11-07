"""Tests des exports CSV et JSON du référentiel, avec isolation par rôle."""
import csv
import io

from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, JournalAction, ScopeSuperviseur, Utilisateur
from entreprises.models import Entreprise, Prospection


class ExportEntreprisesTests(TestCase):
    def setUp(self):
        self.centre_paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation_paris, _ = Formation.objects.get_or_create(
            centre=self.centre_paris,
            nom="Formation Export Lot 11",
        )
        self.centre_lyon, _ = Centre.objects.get_or_create(
            nom="Centre Export Lot 11 Lyon",
            defaults={"departement": "69 - Rhône"},
        )
        self.formation_lyon, _ = Formation.objects.get_or_create(
            centre=self.centre_lyon,
            nom="Formation Export Lot 11 Lyon",
        )
        self.eleve = self.creer_utilisateur(
            "eleve_export_11", Utilisateur.Role.ELEVE, self.centre_paris, self.formation_paris,
        )
        self.eleve_scope = self.creer_utilisateur(
            "eleve_scope_export_11", Utilisateur.Role.ELEVE, self.centre_paris, self.formation_paris,
        )
        self.eleve_hors_scope = self.creer_utilisateur(
            "eleve_hors_export_11", Utilisateur.Role.ELEVE, self.centre_lyon, self.formation_lyon,
        )
        self.superviseur = self.creer_utilisateur(
            "superviseur_export_11", Utilisateur.Role.SUPERVISEUR, self.centre_paris,
        )
        self.autre_superviseur = self.creer_utilisateur(
            "autre_superviseur_export_11", Utilisateur.Role.SUPERVISEUR, self.centre_lyon,
        )
        self.admin = self.creer_utilisateur("admin_export_11", Utilisateur.Role.ADMIN)
        ScopeSuperviseur.objects.create(
            superviseur=self.superviseur,
            centre=self.centre_paris,
            is_active=True,
        )

    def creer_utilisateur(self, username, role, centre=None, formation=None):
        return Utilisateur.objects.create_user(
            username=username,
            password="MotDePasseExport11!",
            role=role,
            centre=centre,
            formation=formation,
            is_valide=True,
        )

    def creer_entreprise(self, eleve, nom, secteur="Informatique", ville="Paris"):
        entreprise = Entreprise.objects.create(nom=nom, secteur=secteur, ville=ville)
        Prospection.objects.create(eleve=eleve, entreprise=entreprise)
        return entreprise

    def csv_rows(self, response):
        contenu = response.content.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(contenu)))

    def get_csv(self, user, params=None):
        self.client.force_login(user)
        return self.client.get(reverse("entreprises:export_csv"), params or {})

    def get_api(self, user=None, params=None):
        if user:
            self.client.force_login(user)
        return self.client.get(reverse("api_entreprises"), params or {}, HTTP_ACCEPT="application/json")

    def test_export_csv_eleve(self):
        visible = self.creer_entreprise(self.eleve, "Entreprise élève CSV")
        self.creer_entreprise(self.eleve_scope, "Entreprise autre élève CSV")

        response = self.get_csv(self.eleve)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv; charset=utf-8"))
        self.assertIn('attachment; filename="entreprises_', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(
            next(csv.reader(io.StringIO(response.content.decode("utf-8-sig")))),
            [
                "nom", "secteur", "ville", "code_postal", "site_web", "contact_nom",
                "contact_email", "contact_telephone", "date_creation", "nb_prospections",
            ],
        )
        self.assertEqual([row["nom"] for row in self.csv_rows(response)], [visible.nom])

    def test_export_csv_superviseur(self):
        propre = self.creer_entreprise(self.superviseur, "Entreprise propre superviseur CSV")
        dans_scope = self.creer_entreprise(self.eleve_scope, "Entreprise scope CSV")
        self.creer_entreprise(self.eleve_hors_scope, "Entreprise hors scope CSV")
        self.creer_entreprise(self.autre_superviseur, "Entreprise autre superviseur CSV")

        response = self.get_csv(self.superviseur)

        self.assertSetEqual(
            {row["nom"] for row in self.csv_rows(response)},
            {propre.nom, dans_scope.nom},
        )

    def test_export_csv_admin(self):
        noms = {
            self.creer_entreprise(self.eleve, "Entreprise admin élève CSV").nom,
            self.creer_entreprise(self.eleve_hors_scope, "Entreprise admin hors scope CSV").nom,
            self.creer_entreprise(self.superviseur, "Entreprise admin superviseur CSV").nom,
        }
        Entreprise.objects.create(nom="Entreprise admin sans prospection CSV")
        noms.add("Entreprise admin sans prospection CSV")

        response = self.get_csv(self.admin)

        self.assertSetEqual({row["nom"] for row in self.csv_rows(response)}, noms)

    def test_export_csv_respecte_filtres(self):
        visible = self.creer_entreprise(self.eleve, "Entreprise filtrée CSV", secteur="Informatique")
        self.creer_entreprise(self.eleve, "Entreprise secteur autre CSV", secteur="Commerce")

        response = self.get_csv(self.eleve, {"secteur": "Informatique"})

        self.assertEqual([row["nom"] for row in self.csv_rows(response)], [visible.nom])

    def test_export_csv_journalise(self):
        self.creer_entreprise(self.eleve, "Entreprise journal CSV")

        response = self.get_csv(self.eleve, {"secteur": "Informatique", "tri": "nom"})

        self.assertEqual(response.status_code, 200)
        journal = JournalAction.objects.get(action=JournalAction.Action.EXPORT_CSV)
        self.assertEqual(journal.utilisateur, self.eleve)
        self.assertEqual(journal.cible_type, "Entreprise")
        self.assertEqual(journal.details, {
            "type": "entreprises",
            "nb_lignes": 1,
            "filtres": {"secteur": "Informatique", "tri": "nom"},
        })

    def test_export_csv_vide_ne_journalise_pas(self):
        response = self.get_csv(self.eleve)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))), [])
        self.assertFalse(JournalAction.objects.filter(action=JournalAction.Action.EXPORT_CSV).exists())

    def test_api_entreprises_eleve(self):
        visible = self.creer_entreprise(self.eleve, "Entreprise élève JSON")
        self.creer_entreprise(self.eleve_scope, "Entreprise privée JSON")

        response = self.get_api(self.eleve)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["nom"] for item in response.json()], [visible.nom])
        self.assertEqual(response.json()[0]["nb_prospections"], 1)

    def test_api_entreprises_superviseur(self):
        propre = self.creer_entreprise(self.superviseur, "Entreprise propre superviseur JSON")
        dans_scope = self.creer_entreprise(self.eleve_scope, "Entreprise scope JSON")
        self.creer_entreprise(self.eleve_hors_scope, "Entreprise hors scope JSON")
        self.creer_entreprise(self.autre_superviseur, "Entreprise autre superviseur JSON")

        response = self.get_api(self.superviseur)

        self.assertEqual(response.status_code, 200)
        self.assertSetEqual({item["nom"] for item in response.json()}, {propre.nom, dans_scope.nom})

    def test_api_entreprises_admin(self):
        noms = {
            self.creer_entreprise(self.eleve, "Entreprise admin élève JSON").nom,
            self.creer_entreprise(self.eleve_hors_scope, "Entreprise admin hors scope JSON").nom,
            self.creer_entreprise(self.superviseur, "Entreprise admin superviseur JSON").nom,
        }
        Entreprise.objects.create(nom="Entreprise admin sans prospection JSON")
        noms.add("Entreprise admin sans prospection JSON")

        response = self.get_api(self.admin)

        self.assertEqual(response.status_code, 200)
        self.assertSetEqual({item["nom"] for item in response.json()}, noms)

    def test_api_entreprises_filtres(self):
        visible = self.creer_entreprise(self.eleve, "Entreprise informatique JSON", secteur="Informatique")
        self.creer_entreprise(self.eleve, "Entreprise commerce JSON", secteur="Commerce")

        response = self.get_api(self.eleve, {"secteur": "Informatique"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["nom"] for item in response.json()], [visible.nom])

    def test_api_entreprises_non_authentifie(self):
        response = self.get_api()
        self.assertEqual(response.status_code, 403)
