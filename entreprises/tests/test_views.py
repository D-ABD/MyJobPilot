"""Tests des vues de prospection élève et de leur isolation."""
from datetime import date

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from comptes.models import Centre, Formation, JournalAction, Utilisateur
from entreprises.models import Entreprise, HistoriqueStatut, Prospection, Statut


class VuesEntreprisesTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS SIO")
        self.autre_centre, _ = Centre.objects.get_or_create(
            nom="Centre vues autre",
            defaults={"departement": "69 - Rhône"},
        )
        self.autre_formation, _ = Formation.objects.get_or_create(
            centre=self.autre_centre,
            nom="BUT vues autre",
        )
        self.eleve = self.creer_eleve("eleve_vues")
        self.autre_eleve = self.creer_eleve("autre_vues", self.autre_centre, self.autre_formation)

    def creer_eleve(self, username, centre=None, formation=None):
        return Utilisateur.objects.create_user(
            username=username,
            password="MotDePasse2026!",
            role=Utilisateur.Role.ELEVE,
            centre=centre or self.centre,
            formation=formation or self.formation,
            is_valide=True,
        )

    def creer_entreprise(self, nom="Entreprise", **kwargs):
        return Entreprise.objects.create(nom=nom, **kwargs)

    def creer_prospection(self, eleve=None, nom="Entreprise", statut=Statut.A_CONTACTER):
        entreprise = self.creer_entreprise(nom)
        return Prospection.objects.create(eleve=eleve or self.eleve, entreprise=entreprise, statut=statut)

    def connecter(self, utilisateur=None):
        self.client.force_login(utilisateur or self.eleve)

    def test_dashboard_sans_authentification_redirige_vers_connexion(self):
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:connexion"), response.url)

    def test_dashboard_eleve_ne_montre_que_ses_prospections(self):
        ma_prospection = self.creer_prospection(nom="ACME")
        autre_prospection = self.creer_prospection(self.autre_eleve, "Beta")
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ACME")
        self.assertNotContains(response, "Beta")
        self.assertEqual(list(response.context["prospections"]), [ma_prospection])
        self.assertNotIn(autre_prospection, response.context["prospections"])

    def test_dashboard_refuse_un_superviseur(self):
        superviseur = Utilisateur.objects.create_user(
            username="superviseur_vues",
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
            username="admin_vues", email="admin-vues@example.com", password="MotDePasse2026!"
        )
        self.connecter(administrateur)
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_filtre_par_statut(self):
        self.creer_prospection(nom="À contacter")
        self.creer_prospection(nom="À relancer", statut=Statut.A_RELANCER)
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"), {"statut": Statut.A_RELANCER})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 1)
        self.assertContains(response, "À relancer")
        self.assertNotContains(response, "badge-statut-a_contacter")

    def test_dashboard_page_limitee_a_vingt_cinq_prospections(self):
        for numero in range(26):
            self.creer_prospection(nom=f"Entreprise vues {numero:02d}")
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["prospections"]), 25)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)

    def test_dashboard_pagination_conserve_les_filtres(self):
        for numero in range(26):
            self.creer_prospection(nom=f"Entreprise vues {numero:02d}")
        self.connecter()
        response = self.client.get(reverse("entreprises:dashboard"), {"q": "Entreprise", "statut": "tous"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("q=Entreprise", response.context["pagination_query"])
        self.assertIn("statut=tous", response.context["pagination_query"])

    def test_get_creation_affiche_le_formulaire(self):
        self.connecter()
        response = self.client.get(reverse("entreprises:create"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("entreprise_form", response.context)

    def test_post_creation_depuis_une_entreprise_existante_cree_historique(self):
        entreprise = self.creer_entreprise("ACME Corp", ville="Paris")
        self.connecter()
        response = self.client.post(
            reverse("entreprises:create"),
            {"entreprise_id": entreprise.pk, "entreprise_nom": entreprise.nom, "statut": Statut.A_CONTACTER},
        )
        prospection = Prospection.objects.get(eleve=self.eleve, entreprise=entreprise)
        self.assertRedirects(response, reverse("entreprises:detail", args=[prospection.pk]))
        historique = prospection.historique.get()
        self.assertEqual(historique.ancien_statut, "")
        self.assertEqual(historique.nouveau_statut, Statut.A_CONTACTER)
        self.assertEqual(historique.auteur, self.eleve)
        self.assertEqual(Entreprise.objects.filter(nom="ACME Corp").count(), 1)

    def test_post_creation_cree_un_nouveau_referentiel_et_une_prospection(self):
        self.connecter()
        response = self.client.post(
            reverse("entreprises:create"),
            {
                "entreprise_nom": "Nouvelle société",
                "nom": "Nouvelle société",
                "secteur": "Conseil",
                "ville": "Paris",
                "statut": Statut.A_CONTACTER,
            },
        )
        entreprise = Entreprise.objects.get(nom="Nouvelle société")
        prospection = Prospection.objects.get(eleve=self.eleve, entreprise=entreprise)
        self.assertRedirects(response, reverse("entreprises:detail", args=[prospection.pk]))

    def test_post_creation_sans_entreprise_est_refuse(self):
        self.connecter()
        response = self.client.post(reverse("entreprises:create"), {"statut": Statut.A_CONTACTER})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Prospection.objects.filter(eleve=self.eleve).exists())

    def test_post_creation_doublon_de_prospection_est_refuse(self):
        prospection = self.creer_prospection(nom="ACME Corp")
        self.connecter()
        response = self.client.post(
            reverse("entreprises:create"),
            {
                "entreprise_id": prospection.entreprise_id,
                "entreprise_nom": prospection.entreprise.nom,
                "statut": Statut.A_CONTACTER,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("entreprises:detail", args=[prospection.pk]),
        )
        self.assertEqual(
            Prospection.objects.filter(
                eleve=self.eleve,
                entreprise=prospection.entreprise,
            ).count(),
            1,
        )

    def test_detail_est_visible_par_le_proprietaire(self):
        prospection = self.creer_prospection()
        self.connecter()
        response = self.client.get(reverse("entreprises:detail", args=[prospection.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["prospection"], prospection)

    def test_detail_hors_propriete_retourne_404(self):
        prospection = self.creer_prospection(self.autre_eleve, "Privée")
        self.connecter()
        response = self.client.get(reverse("entreprises:detail", args=[prospection.pk]))
        self.assertEqual(response.status_code, 404)

    def test_get_modification_affiche_les_donnees_de_la_prospection(self):
        prospection = self.creer_prospection()
        self.connecter()
        response = self.client.get(reverse("entreprises:update", args=[prospection.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["prospection"], prospection)

    def test_post_modification_met_a_jour_la_prospection(self):
        prospection = self.creer_prospection()
        self.connecter()
        response = self.client.post(
            reverse("entreprises:update", args=[prospection.pk]),
            {"statut": Statut.A_CONTACTER, "notes": "Rappeler lundi", "source": "Salon", "entreprise_nom": prospection.entreprise.nom},
        )
        prospection.refresh_from_db()
        self.assertEqual(prospection.notes, "Rappeler lundi")
        self.assertEqual(prospection.source, "Salon")
        self.assertRedirects(response, reverse("entreprises:detail", args=[prospection.pk]))

    def test_post_suppression_efface_la_prospection_et_son_historique_mais_conserve_entreprise(self):
        prospection = self.creer_prospection()
        entreprise = prospection.entreprise
        HistoriqueStatut.objects.create(prospection=prospection, nouveau_statut=Statut.A_CONTACTER, auteur=self.eleve)
        self.connecter()
        response = self.client.post(reverse("entreprises:delete", args=[prospection.pk]))
        self.assertRedirects(response, reverse("entreprises:dashboard"))
        self.assertFalse(Prospection.objects.filter(pk=prospection.pk).exists())
        self.assertFalse(HistoriqueStatut.objects.filter(prospection_id=prospection.pk).exists())
        self.assertTrue(Entreprise.objects.filter(pk=entreprise.pk).exists())

    def test_post_changement_statut_journalise_la_prospection(self):
        prospection = self.creer_prospection()
        self.connecter()
        response = self.client.post(
            reverse("entreprises:changer_statut", args=[prospection.pk]),
            {"nouveau_statut": Statut.A_RELANCER, "date_associee": "2026-11-15", "commentaire": "Rappeler."},
        )
        prospection.refresh_from_db()
        self.assertRedirects(response, reverse("entreprises:detail", args=[prospection.pk]))
        self.assertEqual(prospection.statut, Statut.A_RELANCER)
        self.assertEqual(prospection.date_relance, date(2026, 11, 15))
        historique = prospection.historique.get()
        self.assertEqual(historique.ancien_statut, Statut.A_CONTACTER)
        self.assertEqual(historique.nouveau_statut, Statut.A_RELANCER)
        self.assertEqual(historique.date_associee, date(2026, 11, 15))
        journal = JournalAction.objects.get(action=JournalAction.Action.CHANGEMENT_STATUT)
        self.assertEqual(journal.details["prospection_id"], prospection.pk)
        self.assertEqual(journal.cible_type, "entreprises.Prospection")
        self.assertEqual(journal.cible_id, str(prospection.pk))

    def test_changement_a_relancer_sans_date_est_rejete(self):
        prospection = self.creer_prospection()
        self.connecter()
        response = self.client.post(
            reverse("entreprises:changer_statut", args=[prospection.pk]),
            {"nouveau_statut": Statut.A_RELANCER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("date_associee", response.context["form"].errors)
        prospection.refresh_from_db()
        self.assertEqual(prospection.statut, Statut.A_CONTACTER)
        self.assertFalse(prospection.historique.exists())

    def test_changement_entretien_enregistre_une_date_avec_fuseau(self):
        prospection = self.creer_prospection()
        self.connecter()
        self.client.post(
            reverse("entreprises:changer_statut", args=[prospection.pk]),
            {"nouveau_statut": Statut.ENTRETIEN_PROGRAMME, "date_associee": "2026-11-20"},
        )
        prospection.refresh_from_db()
        self.assertIsNotNone(prospection.date_entretien)
        self.assertTrue(timezone.is_aware(prospection.date_entretien))
        self.assertEqual(timezone.localtime(prospection.date_entretien).date(), date(2026, 11, 20))

    def test_detail_entreprise_ne_revele_pas_les_notes_dune_autre_prospection(self):
        entreprise = self.creer_entreprise("Entreprise partagée")
        Prospection.objects.create(eleve=self.eleve, entreprise=entreprise, notes="Mon secret")
        Prospection.objects.create(eleve=self.autre_eleve, entreprise=entreprise, notes="Secret tiers")
        self.connecter()
        response = self.client.get(reverse("entreprises:detail", args=[Prospection.objects.get(eleve=self.eleve).pk]))
        self.assertContains(response, "Mon secret")
        self.assertNotContains(response, "Secret tiers")

    def test_redirection_apres_login_eleve_valide_vers_dashboard(self):
        self.connecter()
        response = self.client.get(reverse("comptes:redirection_apres_login"))
        self.assertRedirects(response, reverse("entreprises:dashboard"))
