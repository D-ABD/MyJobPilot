import csv
import io

from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, JournalAction, Utilisateur
from entreprises.models import Entreprise, HistoriqueStatut, Prospection, Statut
from rgpd.models import DemandeRGPD


class AdminExportsTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(nom="Centre Paris", defaults={"departement": "75 - Paris"})
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS Test")
        self.admin = Utilisateur.objects.create_user(username="admin_csv", password="p", role="admin", is_staff=True)
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_csv", password="p", role="eleve", centre=self.centre,
            formation=self.formation, is_valide=True,
        )
        entreprise = Entreprise.objects.create(nom="CSV Entreprise", ville="Paris")
        self.prospection = Prospection.objects.create(eleve=self.eleve, entreprise=entreprise)
        HistoriqueStatut.objects.create(
            prospection=self.prospection, ancien_statut="", nouveau_statut=Statut.A_CONTACTER,
            auteur=None, commentaire="Création",
        )
        DemandeRGPD.objects.create(utilisateur=self.eleve, type="acces")

    def _csv(self, route, headers):
        self.client.force_login(self.admin)
        response = self.client.get(reverse(route))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], headers)
        action = JournalAction.objects.filter(action=JournalAction.Action.EXPORT_CSV).latest("date")
        self.assertGreaterEqual(action.details["nb_lignes"], 1)
        return rows

    def test_export_eleves_colonnes_et_bom(self):
        rows = self._csv("admin_dashboard:export_eleves", [
            "username", "email", "first_name", "last_name", "centre", "formation",
            "is_valide", "date_validation", "valide_par", "motif_refus", "date_joined", "nb_prospections",
        ])
        self.assertEqual(rows[1][0], self.eleve.username)

    def test_export_prospections_colonnes(self):
        rows = self._csv("admin_dashboard:export_prospections", [
            "eleve_username", "entreprise_nom", "entreprise_ville", "statut",
            "date_creation", "date_modification", "date_relance", "date_candidature",
            "date_entretien", "date_refus", "date_acceptation",
        ])
        self.assertEqual(rows[1][0], self.eleve.username)

    def test_export_historique_colonnes(self):
        rows = self._csv("admin_dashboard:export_historique", [
            "eleve_username", "entreprise_nom", "ancien_statut", "nouveau_statut",
            "date_changement", "auteur_username", "commentaire", "date_associee",
        ])
        self.assertEqual(rows[1][5], "système")

    def test_export_demandes_rgpd_colonnes(self):
        rows = self._csv("admin_dashboard:export_demandes_rgpd", [
            "utilisateur_username", "type", "statut", "date_demande",
            "date_traitement", "traitee_par_username", "motif_refus", "description",
        ])
        self.assertEqual(rows[1][0], self.eleve.username)

    def test_non_admin_refuse_export(self):
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("admin_dashboard:export_eleves"))
        self.assertEqual(response.status_code, 403)
