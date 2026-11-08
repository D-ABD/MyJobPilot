"""Tests des actions staff sur les élèves et leurs prospections."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, JournalAction, Notification, ScopeSuperviseur, TypeNotification, Utilisateur
from entreprises.models import Entreprise, Prospection, Statut, TypeContrat


class ActionsStaffEleveTests(TestCase):
    def setUp(self):
        self.centre_paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation_paris, _ = Formation.objects.get_or_create(centre=self.centre_paris, nom="BTS SIO")
        self.centre_lyon, _ = Centre.objects.get_or_create(
            nom="Centre Lot 4 Lyon",
            defaults={"departement": "69 - Rhône"},
        )
        self.formation_lyon, _ = Formation.objects.get_or_create(
            centre=self.centre_lyon,
            nom="Formation Lot 4 Lyon",
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="superviseur_lot4",
            password="mot-de-passe",
            role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre_paris,
            is_staff=True,
            is_valide=True,
        )
        self.eleve_paris = self.creer_eleve("eleve_lot4_paris", self.centre_paris, self.formation_paris)
        self.eleve_lyon = self.creer_eleve("eleve_lot4_lyon", self.centre_lyon, self.formation_lyon)
        self.admin = Utilisateur.objects.create_superuser(
            username="admin_lot4",
            email="admin-lot4@example.com",
            password="mot-de-passe",
        )

    def creer_eleve(self, username, centre, formation):
        return Utilisateur.objects.create_user(
            username=username,
            password="mot-de-passe",
            role=Utilisateur.Role.ELEVE,
            centre=centre,
            formation=formation,
            is_valide=True,
        )

    def creer_entreprise(self, nom):
        return Entreprise.objects.create(nom=nom)

    def connecter(self, user):
        self.client.force_login(user)

    def test_superviseur_peut_changer_centre_dans_son_scope_et_journalise(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_lyon)
        self.connecter(self.superviseur)
        response = self.client.post(
            reverse("staff:changer_centre", args=[self.eleve_paris.pk]),
            {"centre": self.centre_lyon.pk},
        )
        self.assertRedirects(response, reverse("staff:detail_eleve", args=[self.eleve_paris.pk]))
        self.eleve_paris.refresh_from_db()
        self.assertEqual(self.eleve_paris.centre_id, self.centre_lyon.pk)
        journal = JournalAction.objects.get(action=JournalAction.Action.CHANGEMENT_CENTRE)
        self.assertEqual(
            journal.details,
            {"ancien_centre_id": self.centre_paris.pk, "nouveau_centre_id": self.centre_lyon.pk, "eleve_id": self.eleve_paris.pk},
        )

    def test_superviseur_ne_peut_pas_changer_vers_un_centre_hors_scope(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        self.connecter(self.superviseur)
        response = self.client.post(
            reverse("staff:changer_centre", args=[self.eleve_paris.pk]),
            {"centre": self.centre_lyon.pk},
        )
        self.assertEqual(response.status_code, 403)
        self.eleve_paris.refresh_from_db()
        self.assertEqual(self.eleve_paris.centre_id, self.centre_paris.pk)

    def test_superviseur_ne_peut_pas_changer_le_centre_d_un_eleve_hors_scope(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        self.connecter(self.superviseur)
        response = self.client.get(reverse("staff:changer_centre", args=[self.eleve_lyon.pk]))
        self.assertEqual(response.status_code, 403)

    def test_admin_peut_changer_le_centre_de_nimporte_quel_eleve(self):
        self.connecter(self.admin)
        response = self.client.post(
            reverse("staff:changer_centre", args=[self.eleve_lyon.pk]),
            {"centre": self.centre_paris.pk},
        )
        self.assertRedirects(response, reverse("staff:detail_eleve", args=[self.eleve_lyon.pk]))
        self.eleve_lyon.refresh_from_db()
        self.assertEqual(self.eleve_lyon.centre_id, self.centre_paris.pk)
        self.assertTrue(JournalAction.objects.filter(action=JournalAction.Action.CHANGEMENT_CENTRE).exists())

    def test_changement_de_centre_conserve_les_prospections_de_leleve(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_lyon)
        entreprise = self.creer_entreprise("Prospection conservée")
        prospection = Prospection.objects.create(eleve=self.eleve_paris, entreprise=entreprise)
        self.connecter(self.superviseur)
        self.client.post(
            reverse("staff:changer_centre", args=[self.eleve_paris.pk]),
            {"centre": self.centre_lyon.pk},
        )
        self.assertTrue(Prospection.objects.filter(pk=prospection.pk, eleve=self.eleve_paris).exists())

    def test_superviseur_peut_ajouter_une_prospection_depuis_le_referentiel(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        entreprise = self.creer_entreprise("Prospection staff")
        self.connecter(self.superviseur)
        response = self.client.post(
            reverse("staff:ajouter_entreprise", args=[self.eleve_paris.pk]),
            {"entreprise_id": entreprise.pk, "entreprise_nom": entreprise.nom, "statut": Statut.A_CONTACTER, "type_contrat": TypeContrat.STAGE},
        )
        self.assertRedirects(response, reverse("staff:detail_eleve", args=[self.eleve_paris.pk]))
        prospection = Prospection.objects.get(eleve=self.eleve_paris, entreprise=entreprise)
        self.assertEqual(prospection.statut, Statut.A_CONTACTER)
        self.assertEqual(prospection.type_contrat, TypeContrat.STAGE)
        self.assertTrue(
            prospection.historique.filter(
                ancien_statut="", nouveau_statut=Statut.A_CONTACTER, auteur=self.superviseur
            ).exists()
        )
        journal = JournalAction.objects.get(action=JournalAction.Action.ACTION_STAFF_ELEVE)
        self.assertEqual(
            journal.details,
            {"prospection_id": prospection.pk, "eleve_id": self.eleve_paris.pk, "action": "ajout_prospection"},
        )
        self.assertEqual(journal.cible_type, "entreprises.Prospection")
        self.assertEqual(journal.cible_id, str(prospection.pk))
        self.assertFalse(Notification.objects.filter(
            destinataire=self.eleve_paris, type=TypeNotification.AJOUT_PROSPECTION,
        ).exists())

    def test_dashboard_staff_filtre_par_type_contrat(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        stage = Prospection.objects.create(eleve=self.eleve_paris, entreprise=self.creer_entreprise("Stage staff"), type_contrat=TypeContrat.STAGE)
        Prospection.objects.create(eleve=self.eleve_paris, entreprise=self.creer_entreprise("Alternance staff"), type_contrat=TypeContrat.ALTERNANCE)
        self.connecter(self.superviseur)
        response = self.client.get(reverse("staff:dashboard"), {"type_contrat": TypeContrat.STAGE})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["eleves"]), [self.eleve_paris])
        self.assertEqual(response.context["total_count"], 1)

    def test_superviseur_choisit_le_type_de_contrat(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        entreprise = self.creer_entreprise("Prospection stage staff")
        self.connecter(self.superviseur)
        response = self.client.post(reverse("staff:ajouter_entreprise", args=[self.eleve_paris.pk]), {
            "entreprise_id": entreprise.pk, "entreprise_nom": entreprise.nom,
            "statut": Statut.A_CONTACTER, "type_contrat": TypeContrat.STAGE,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Prospection.objects.get(eleve=self.eleve_paris, entreprise=entreprise).type_contrat, TypeContrat.STAGE)

    def test_superviseur_peut_creer_une_entreprise_et_sa_prospection(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        self.connecter(self.superviseur)
        response = self.client.post(
            reverse("staff:ajouter_entreprise", args=[self.eleve_paris.pk]),
            {
                "entreprise_nom": "Nouvelle entreprise staff",
                "nom": "Nouvelle entreprise staff",
                "ville": "Paris",
                "statut": Statut.A_CONTACTER,
                "type_contrat": TypeContrat.ALTERNANCE,
            },
        )
        entreprise = Entreprise.objects.get(nom="Nouvelle entreprise staff")
        self.assertRedirects(response, reverse("staff:detail_eleve", args=[self.eleve_paris.pk]))
        self.assertTrue(Prospection.objects.filter(eleve=self.eleve_paris, entreprise=entreprise).exists())

    def test_superviseur_ne_peut_pas_ajouter_pour_un_eleve_hors_scope(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        self.connecter(self.superviseur)
        response = self.client.post(
            reverse("staff:ajouter_entreprise", args=[self.eleve_lyon.pk]),
            {"entreprise_nom": "Interdit", "statut": Statut.A_CONTACTER},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Entreprise.objects.filter(nom="Interdit").exists())

    def test_superviseur_ne_peut_pas_creer_un_doublon_de_prospection(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        entreprise = self.creer_entreprise("Déjà prospectée")
        Prospection.objects.create(eleve=self.eleve_paris, entreprise=entreprise)
        self.connecter(self.superviseur)
        response = self.client.post(
            reverse("staff:ajouter_entreprise", args=[self.eleve_paris.pk]),
            {"entreprise_id": entreprise.pk, "entreprise_nom": entreprise.nom, "statut": Statut.A_CONTACTER, "type_contrat": TypeContrat.ALTERNANCE},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Prospection.objects.filter(eleve=self.eleve_paris).count(), 1)

    def test_admin_peut_ajouter_une_prospection_a_nimporte_quel_eleve(self):
        entreprise = self.creer_entreprise("Prospection admin")
        self.connecter(self.admin)
        response = self.client.post(
            reverse("staff:ajouter_entreprise", args=[self.eleve_lyon.pk]),
            {"entreprise_id": entreprise.pk, "entreprise_nom": entreprise.nom, "statut": Statut.A_CONTACTER, "type_contrat": TypeContrat.ALTERNANCE},
        )
        self.assertRedirects(response, reverse("staff:detail_eleve", args=[self.eleve_lyon.pk]))
        self.assertTrue(Prospection.objects.filter(eleve=self.eleve_lyon, entreprise=entreprise).exists())
        self.assertFalse(Notification.objects.filter(
            destinataire=self.eleve_lyon, type=TypeNotification.AJOUT_PROSPECTION,
        ).exists())

    def test_detail_staff_est_accessible_a_ladmin(self):
        self.connecter(self.admin)
        response = self.client.get(reverse("staff:detail_eleve", args=[self.eleve_lyon.pk]))
        self.assertEqual(response.status_code, 200)

    def test_formulaire_superviseur_ne_propose_que_ses_centres(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris)
        self.connecter(self.superviseur)
        response = self.client.get(reverse("staff:changer_centre", args=[self.eleve_paris.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["form"].fields["centre"].queryset), [self.centre_paris])

    def test_eleve_ne_peut_pas_utiliser_les_actions_staff(self):
        self.connecter(self.eleve_paris)
        changer = self.client.get(reverse("staff:changer_centre", args=[self.eleve_paris.pk]))
        ajouter = self.client.post(
            reverse("staff:ajouter_entreprise", args=[self.eleve_paris.pk]),
            {"entreprise_nom": "Interdit", "statut": Statut.A_CONTACTER},
        )
        self.assertEqual(changer.status_code, 403)
        self.assertEqual(ajouter.status_code, 403)

