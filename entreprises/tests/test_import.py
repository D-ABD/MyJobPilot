"""Tests de l'import CSV des entreprises, des permissions et du fichier exemple."""
import csv
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, JournalAction, Utilisateur
from entreprises.models import Entreprise


class ImportEntreprisesTests(TestCase):
    def setUp(self):
        self.centre_paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.admin = self.creer_utilisateur("admin_import_ent_12", Utilisateur.Role.ADMIN)
        self.eleve = self.creer_utilisateur(
            "eleve_import_ent_12", Utilisateur.Role.ELEVE, self.centre_paris,
        )
        self.superviseur = self.creer_utilisateur(
            "superviseur_import_ent_12", Utilisateur.Role.SUPERVISEUR, self.centre_paris,
        )

    def creer_utilisateur(self, username, role, centre=None):
        return Utilisateur.objects.create_user(
            username=username,
            password="MotDePasseImport12!",
            role=role,
            centre=centre,
            is_valide=True,
        )

    def csv_file(self, rows, filename="entreprises.csv", headers=None):
        if headers is None:
            headers = [
                "nom", "secteur", "ville", "code_postal", "site_web",
                "contact_nom", "contact_email", "contact_telephone",
            ]
        contenu = io.StringIO(newline="")
        writer = csv.writer(contenu)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return SimpleUploadedFile(filename, contenu.getvalue().encode("utf-8"), content_type="text/csv")

    def import_post(self, fichier, user=None):
        self.client.force_login(user or self.admin)
        return self.client.post(
            reverse("admin_dashboard:import_entreprises"),
            {"fichier": fichier},
        )

    def rapport(self, response):
        self.assertEqual(response.status_code, 200)
        return response.context["rapport"]

    def test_import_valide(self):
        fichier = self.csv_file([
            ["ACME Corp", "Informatique", "Paris", "75001", "https://acme.fr", "Jean Dupont", "jean+test@example.com", "0123456789"],
            ["Super Corp", "Finance", "Lyon", "69001", "http://supercorp.fr", "Marie Martin", "marie@example.com", "0987654321"],
            ["North Corp", "Services", "Marseille", "13001", "https://north.example", "Alex Smith", "alex@example.co.uk", "02012345678"],
        ])

        response = self.import_post(fichier)
        rapport = self.rapport(response)

        self.assertEqual(rapport["total"], 3)
        self.assertEqual(rapport["crees"], 3)
        self.assertEqual(rapport["rejetes"], 0)
        self.assertEqual(Entreprise.objects.count(), 3)
        self.assertEqual(Entreprise.objects.get(nom="North Corp").code_postal, "13001")

    def test_import_nom_existant(self):
        Entreprise.objects.create(nom="ACME Corp")
        fichier = self.csv_file([["acme corp", "Informatique", "Paris", "75001", "", "", "", ""]])

        rapport = self.rapport(self.import_post(fichier))

        self.assertEqual((rapport["total"], rapport["crees"], rapport["rejetes"]), (1, 0, 1))
        self.assertEqual(rapport["erreurs"][0]["raison"], "Nom déjà utilisé")
        self.assertEqual(Entreprise.objects.count(), 1)

    def test_import_nom_vide(self):
        fichier = self.csv_file([["   ", "Informatique", "Paris", "75001", "", "", "", ""]])

        rapport = self.rapport(self.import_post(fichier))

        self.assertEqual((rapport["crees"], rapport["rejetes"]), (0, 1))
        self.assertEqual(rapport["erreurs"][0]["raison"], "Nom obligatoire")

    def test_import_email_invalide(self):
        fichier = self.csv_file([["ACME Corp", "Informatique", "Paris", "75001", "", "", "pas-un-email", ""]])

        rapport = self.rapport(self.import_post(fichier))

        self.assertEqual((rapport["crees"], rapport["rejetes"]), (0, 1))
        self.assertEqual(rapport["erreurs"][0]["raison"], "Email invalide")

    def test_import_code_postal_invalide(self):
        fichier = self.csv_file([["ACME Corp", "Informatique", "Paris", "12!", "", "", "", ""]])

        rapport = self.rapport(self.import_post(fichier))

        self.assertEqual((rapport["crees"], rapport["rejetes"]), (0, 1))
        self.assertEqual(rapport["erreurs"][0]["raison"], "Code postal invalide (5 chiffres requis)")

    def test_import_code_postal_etranger_rejete(self):
        fichier = self.csv_file([["ACME Corp", "Informatique", "Paris", "1000", "", "", "", ""]])

        rapport = self.rapport(self.import_post(fichier))

        self.assertEqual((rapport["crees"], rapport["rejetes"]), (0, 1))
        self.assertEqual(rapport["erreurs"][0]["raison"], "Code postal invalide (5 chiffres requis)")

    def test_import_journalise(self):
        fichier = self.csv_file([
            ["Créée Corp", "Informatique", "Paris", "75001", "", "", "", ""],
            ["", "Finance", "Lyon", "69001", "", "", "", ""],
        ])

        self.import_post(fichier)

        journal = JournalAction.objects.get(action=JournalAction.Action.IMPORT_CSV)
        self.assertEqual(journal.utilisateur, self.admin)
        self.assertEqual(journal.details, {
            "type": "entreprises", "total": 2, "crees": 1, "rejetes": 1,
        })

    def test_import_non_admin(self):
        fichier_eleve = self.csv_file([["Entreprise élève", "", "", "", "", "", "", ""]])
        fichier_superviseur = self.csv_file([["Entreprise superviseur", "", "", "", "", "", "", ""]])

        response_eleve = self.import_post(fichier_eleve, self.eleve)
        response_superviseur = self.import_post(fichier_superviseur, self.superviseur)

        self.assertEqual(response_eleve.status_code, 403)
        self.assertEqual(response_superviseur.status_code, 403)
        self.assertEqual(Entreprise.objects.count(), 0)
        self.assertFalse(JournalAction.objects.filter(action=JournalAction.Action.IMPORT_CSV).exists())

    def test_exemple_csv_telechargeable(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin_dashboard:import_entreprises_exemple"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv; charset=utf-8"))
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="entreprises_exemple.csv"')
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        lignes = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(lignes[0], [
            "nom", "secteur", "ville", "code_postal", "site_web",
            "contact_nom", "contact_email", "contact_telephone",
        ])
        self.assertEqual(lignes[1][0], "ACME Corp")
        self.assertEqual(lignes[2][0], "Super Corp")
