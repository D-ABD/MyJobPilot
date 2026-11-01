"""Tests des vues de prospection élève."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, JournalAction, Utilisateur
from entreprises.models import Entreprise, HistoriqueStatut, Statut


class VuesEntreprisesTests(TestCase):
    def setUp(self):
        self.centre = Centre.objects.create(nom="Centre vues", departement="75 - Paris")
        self.formation = Formation.objects.create(centre=self.centre, nom="BTS Test")
        self.autre_centre = Centre.objects.create(nom="Centre autre", departement="69 - Rhône")
        self.autre_formation = Formation.objects.create(centre=self.autre_centre, nom="BUT Test")
        self.eleve = self.creer_eleve("eleve")
        self.autre_eleve = self.creer_eleve("autre")
        self.donnees_entreprise = {"nom": "ACME Corp", "secteur": "Conseil", "ville": "Paris"}

    def creer_eleve(self, username):
        return Utilisateur.objects.create_user(
            username=username,
            password="MotDePasse2026!",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def creer_entreprise(self, eleve=None, nom="Entreprise"):
        return Entreprise.objects.create(eleve=eleve or self.eleve, nom=nom)

    def connecter(self, utilisateur=None):
        self.client.force_login(utilisateur or self.eleve)

    def test_dashboard_sans_authentification_redirige_vers_connexion(self):
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    def test_dashboard_eleve_ne_montre_que_ses_entreprises(self):
        entreprise_a = self.creer_entreprise(nom="ACME")
        entreprise_b = self.creer_entreprise(self.autre_eleve, "Beta")
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ACME")
        self.assertNotContains(response, "Beta")
        self.assertEqual(list(response.context["entreprises"]), [entreprise_a])
        self.assertNotIn(entreprise_b, response.context["entreprises"])

    def test_dashboard_refuse_un_superviseur(self):
        superviseur = Utilisateur.objects.create_user(
            username="superviseur",
            password="MotDePasse2026!",
            role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre,
            is_staff=True,
            is_valide=True,
        )
        self.connecter(superviseur)
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_refuse_un_administrateur(self):
        administrateur = Utilisateur.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="MotDePasse2026!",
        )
        self.connecter(administrateur)
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_filtre_par_statut(self):
        self.creer_entreprise(nom="À contacter")
        Entreprise.objects.create(eleve=self.eleve, nom="À relancer", statut=Statut.A_RELANCER)
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"), {"statut": Statut.A_RELANCER})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 1)
        self.assertContains(response, "À relancer")
        self.assertNotContains(response, "À contacter")

    def test_dashboard_page_limitee_a_vingt_cinq_entreprises(self):
        for numero in range(26):
            self.creer_entreprise(nom=f"Entreprise {numero:02d}")
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["entreprises"]), 25)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)

    def test_dashboard_pagination_conserve_les_filtres(self):
        for numero in range(26):
            self.creer_entreprise(nom=f"Entreprise {numero:02d}")
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"), {"q": "Entreprise", "statut": "tous"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("q=Entreprise", response.context["pagination_query"])
        self.assertIn("statut=tous", response.context["pagination_query"])

    def test_get_creation_affiche_le_formulaire(self):
        self.connecter()
        response = self.client.get(reverse("entreprises:create"))
        self.assertEqual(response.status_code, 200)

    def test_post_creation_cree_entreprise_historique_et_redirige(self):
        self.connecter()
        response = self.client.post(reverse("entreprises:create"), self.donnees_entreprise)
        entreprise = Entreprise.objects.get(nom="ACME Corp")
        self.assertRedirects(response, reverse("entreprises:detail", args=[entreprise.pk]))
        self.assertEqual(entreprise.eleve, self.eleve)
        self.assertEqual(entreprise.statut, Statut.A_CONTACTER)
        historique = entreprise.historique.get()
        self.assertEqual(historique.ancien_statut, "")
        self.assertEqual(historique.nouveau_statut, Statut.A_CONTACTER)
        self.assertEqual(historique.auteur, self.eleve)
        self.assertFalse(JournalAction.objects.filter(action=JournalAction.Action.CHANGEMENT_STATUT).exists())

    def test_post_creation_invalide_affiche_les_erreurs(self):
        self.connecter()
        response = self.client.post(reverse("entreprises:create"), {"nom": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Entreprise.objects.filter(eleve=self.eleve).exists())

    def test_detail_est_visible_par_le_proprietaire(self):
        entreprise = self.creer_entreprise()
        self.connecter()
        response = self.client.get(reverse("entreprises:detail", args=[entreprise.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["entreprise"], entreprise)

    def test_detail_hors_propriete_retourne_404(self):
        entreprise = self.creer_entreprise(self.autre_eleve, "Privée")
        self.connecter()
        response = self.client.get(reverse("entreprises:detail", args=[entreprise.pk]))
        self.assertEqual(response.status_code, 404)

    def test_get_modification_affiche_les_donnees(self):
        entreprise = self.creer_entreprise()
        self.connecter()
        response = self.client.get(reverse("entreprises:update", args=[entreprise.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].instance, entreprise)

    def test_post_modification_met_a_jour_et_redirige(self):
        entreprise = self.creer_entreprise()
        self.connecter()
        response = self.client.post(
            reverse("entreprises:update", args=[entreprise.pk]),
            {"nom": "Nom modifié", "ville": "Lyon"},
        )
        entreprise.refresh_from_db()
        self.assertEqual(entreprise.nom, "Nom modifié")
        self.assertEqual(entreprise.ville, "Lyon")
        self.assertRedirects(response, reverse("entreprises:detail", args=[entreprise.pk]))

    def test_get_suppression_affiche_confirmation(self):
        entreprise = self.creer_entreprise()
        self.connecter()
        response = self.client.get(reverse("entreprises:delete", args=[entreprise.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_suppression_efface_entreprise_et_historique(self):
        entreprise = self.creer_entreprise()
        HistoriqueStatut.objects.create(
            entreprise=entreprise,
            nouveau_statut=Statut.A_CONTACTER,
            auteur=self.eleve,
        )
        self.connecter()
        response = self.client.post(reverse("entreprises:delete", args=[entreprise.pk]))
        self.assertRedirects(response, reverse("entreprises:dashboard"))
        self.assertFalse(Entreprise.objects.filter(pk=entreprise.pk).exists())
        self.assertFalse(HistoriqueStatut.objects.filter(entreprise_id=entreprise.pk).exists())

    def test_post_changement_statut_cree_historique_et_journal(self):
        entreprise = self.creer_entreprise()
        self.connecter()
        response = self.client.post(
            reverse("entreprises:changer_statut", args=[entreprise.pk]),
            {
                "nouveau_statut": Statut.A_RELANCER,
                "date_associee": "2026-11-15",
                "commentaire": "Relancer après l'appel.",
            },
        )
        entreprise.refresh_from_db()
        self.assertRedirects(response, reverse("entreprises:detail", args=[entreprise.pk]))
        self.assertEqual(entreprise.statut, Statut.A_RELANCER)
        self.assertEqual(entreprise.date_relance, date(2026, 11, 15))
        historique = entreprise.historique.get()
        self.assertEqual(historique.ancien_statut, Statut.A_CONTACTER)
        self.assertEqual(historique.nouveau_statut, Statut.A_RELANCER)
        self.assertEqual(historique.date_associee, date(2026, 11, 15))
        entree_journal = JournalAction.objects.get(action=JournalAction.Action.CHANGEMENT_STATUT)
        self.assertEqual(entree_journal.details["entreprise_id"], entreprise.pk)
        self.assertEqual(entree_journal.details["ancien_statut"], Statut.A_CONTACTER)
        self.assertEqual(entree_journal.details["nouveau_statut"], Statut.A_RELANCER)

    def test_changement_a_relancer_sans_date_est_rejete(self):
        entreprise = self.creer_entreprise()
        self.connecter()
        response = self.client.post(
            reverse("entreprises:changer_statut", args=[entreprise.pk]),
            {"nouveau_statut": Statut.A_RELANCER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("date_associee", response.context["form"].errors)
        entreprise.refresh_from_db()
        self.assertEqual(entreprise.statut, Statut.A_CONTACTER)
        self.assertFalse(entreprise.historique.exists())

    def test_changement_entretien_enregistre_la_date_associee(self):
        entreprise = self.creer_entreprise()
        self.connecter()
        self.client.post(
            reverse("entreprises:changer_statut", args=[entreprise.pk]),
            {"nouveau_statut": Statut.ENTRETIEN_PROGRAMME, "date_associee": "2026-11-20"},
        )
        entreprise.refresh_from_db()
        self.assertIsNotNone(entreprise.date_entretien)
        self.assertEqual(entreprise.date_entretien.date(), date(2026, 11, 20))

    def test_changement_de_statut_a_contacter_ne_demande_pas_de_date(self):
        entreprise = self.creer_entreprise()
        entreprise.statut = Statut.REFUS
        entreprise.save()
        self.connecter()
        response = self.client.post(
            reverse("entreprises:changer_statut", args=[entreprise.pk]),
            {"nouveau_statut": Statut.A_CONTACTER},
        )
        self.assertRedirects(response, reverse("entreprises:detail", args=[entreprise.pk]))
        entreprise.refresh_from_db()
        self.assertEqual(entreprise.statut, Statut.A_CONTACTER)

    def test_redirection_apres_login_eleve_valide_vers_dashboard(self):
        self.connecter()
        response = self.client.get(reverse("comptes:redirection_apres_login"))
        self.assertRedirects(response, reverse("entreprises:dashboard"))
