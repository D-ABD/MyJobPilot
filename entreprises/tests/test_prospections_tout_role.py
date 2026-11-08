"""Tests des prospections visibles et créables selon le rôle."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import (
    Centre, Formation, JournalAction, Notification, ScopeSuperviseur,
    TypeNotification, Utilisateur,
)
from entreprises.forms import ProspectionFormToutRole
from entreprises.models import Entreprise, HistoriqueStatut, Prospection, Statut, TypeContrat


class ProspectionsTousRolesTests(TestCase):
    def setUp(self):
        self.centre_paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation_paris, _ = Formation.objects.get_or_create(
            centre=self.centre_paris,
            nom="BTS Lot 8d",
        )
        self.centre_lyon, _ = Centre.objects.get_or_create(
            nom="Centre Lot 8d Lyon",
            defaults={"departement": "69 - Rhône"},
        )
        self.formation_lyon, _ = Formation.objects.get_or_create(
            centre=self.centre_lyon,
            nom="BTS Lot 8d Lyon",
        )
        self.eleve = self.creer_utilisateur(
            "eleve_8d", Utilisateur.Role.ELEVE, self.centre_paris, self.formation_paris,
        )
        self.eleve_scope = self.creer_utilisateur(
            "eleve_scope_8d", Utilisateur.Role.ELEVE, self.centre_paris, self.formation_paris,
        )
        self.eleve_hors_scope = self.creer_utilisateur(
            "eleve_hors_scope_8d", Utilisateur.Role.ELEVE, self.centre_lyon, self.formation_lyon,
        )
        self.superviseur = self.creer_utilisateur(
            "superviseur_8d", Utilisateur.Role.SUPERVISEUR, self.centre_paris,
        )
        self.autre_superviseur = self.creer_utilisateur(
            "autre_superviseur_8d", Utilisateur.Role.SUPERVISEUR, self.centre_lyon,
        )
        self.admin = self.creer_utilisateur("admin_8d", Utilisateur.Role.ADMIN, is_staff=True)
        self.autre_admin = self.creer_utilisateur("autre_admin_8d", Utilisateur.Role.ADMIN, is_staff=True)
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_paris, is_active=True)

    def creer_utilisateur(self, username, role, centre=None, formation=None, is_staff=False):
        return Utilisateur.objects.create_user(
            username=username,
            password="MotDePasse2026!",
            role=role,
            centre=centre,
            formation=formation,
            is_valide=True,
            is_staff=is_staff,
        )

    def creer_prospection(self, proprietaire, nom):
        entreprise = Entreprise.objects.create(nom=nom)
        return Prospection.objects.create(eleve=proprietaire, entreprise=entreprise)

    def poster_creation(self, auteur, proprietaire, entreprise, **extra):
        self.client.force_login(auteur)
        return self.client.post(
            reverse("entreprises:prospection_create_tout_role"),
            {
                "proprietaire": proprietaire.pk,
                "entreprise_id": entreprise.pk,
                "entreprise_nom": entreprise.nom,
                "statut": Statut.A_CONTACTER,
                "type_contrat": TypeContrat.STAGE,
                **extra,
            },
        )

    def test_queryset_proprietaire_eleve_contient_uniquement_lui_meme(self):
        form = ProspectionFormToutRole(request=type("Request", (), {"user": self.eleve})())
        self.assertEqual(
            list(form.fields["proprietaire"].queryset),
            [self.eleve],
        )
        self.assertTrue(form.fields["proprietaire"].widget.is_hidden)

    def test_queryset_proprietaire_superviseur_contient_lui_et_son_scope(self):
        form = ProspectionFormToutRole(request=type("Request", (), {"user": self.superviseur})())
        self.assertSetEqual(
            set(form.fields["proprietaire"].queryset),
            {self.superviseur, self.eleve, self.eleve_scope},
        )
        self.assertNotIn(self.eleve_hors_scope, form.fields["proprietaire"].queryset)
        self.assertNotIn(self.autre_superviseur, form.fields["proprietaire"].queryset)

    def test_queryset_proprietaire_admin_contient_eleve_superviseurs_et_lui_meme(self):
        form = ProspectionFormToutRole(request=type("Request", (), {"user": self.admin})())
        self.assertSetEqual(
            set(form.fields["proprietaire"].queryset),
            {
                self.admin, self.eleve, self.eleve_scope, self.eleve_hors_scope,
                self.superviseur, self.autre_superviseur,
            },
        )
        self.assertNotIn(self.autre_admin, form.fields["proprietaire"].queryset)

    def test_liste_eleve_isole_ses_prospections(self):
        ma = self.creer_prospection(self.eleve, "Prospection privée élève")
        self.creer_prospection(self.eleve_scope, "Prospection autre élève")
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("entreprises:prospections_toutes"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["prospections"]), [ma])

    def test_liste_superviseur_inclut_ses_prospections_et_son_scope_uniquement(self):
        propre = self.creer_prospection(self.superviseur, "Prospection propre superviseur")
        eleve_scope = self.creer_prospection(self.eleve_scope, "Prospection élève du scope")
        self.creer_prospection(self.eleve_hors_scope, "Prospection hors scope")
        self.creer_prospection(self.autre_superviseur, "Prospection autre superviseur")
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("entreprises:prospections_toutes"))
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(
            set(response.context["prospections"]),
            {propre, eleve_scope},
        )
        self.assertEqual(response.context["total_count"], 2)
        contenu = response.content.decode()
        self.assertEqual(contenu.count(">Modifier</a>"), 1)
        self.assertEqual(contenu.count(">Supprimer</a>"), 1)
        self.assertEqual(contenu.count(">Changer le statut</a>"), 2)

    def test_liste_admin_inclut_toutes_les_prospections(self):
        proprietaires = (
            self.eleve, self.eleve_hors_scope, self.superviseur,
            self.autre_superviseur, self.admin,
        )
        attendues = {
            self.creer_prospection(proprietaire, f"Prospection admin {index}")
            for index, proprietaire in enumerate(proprietaires)
        }
        self.client.force_login(self.admin)
        response = self.client.get(reverse("entreprises:prospections_toutes"))
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(response.context["prospections"]), attendues)
        self.assertEqual(response.context["total_count"], len(attendues))
        self.assertEqual(response.content.decode().count(">Modifier</a>"), len(attendues))

    def test_eleve_cree_une_prospection_pour_lui_meme_sans_notification_staff(self):
        entreprise = Entreprise.objects.create(nom="Création élève pour soi")
        response = self.poster_creation(self.eleve, self.eleve, entreprise)
        self.assertEqual(response.status_code, 302)
        prospection = Prospection.objects.get(eleve=self.eleve, entreprise=entreprise)
        self.assertEqual(prospection.type_contrat, TypeContrat.STAGE)
        self.assertFalse(JournalAction.objects.filter(
            action=JournalAction.Action.ACTION_STAFF_ELEVE,
            cible_id=str(prospection.pk),
        ).exists())
        self.assertFalse(Notification.objects.filter(
            destinataire=self.eleve,
            type=TypeNotification.AJOUT_PROSPECTION,
        ).exists())

    def test_superviseur_cree_une_prospection_pour_lui_meme(self):
        entreprise = Entreprise.objects.create(nom="Création superviseur pour soi")
        response = self.poster_creation(self.superviseur, self.superviseur, entreprise)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Prospection.objects.filter(eleve=self.superviseur, entreprise=entreprise).exists())
        self.assertFalse(JournalAction.objects.filter(
            action=JournalAction.Action.ACTION_STAFF_ELEVE,
        ).exists())

    def test_superviseur_cree_pour_un_eleve_de_scope_sans_notification(self):
        entreprise = Entreprise.objects.create(nom="Création superviseur pour élève")
        response = self.poster_creation(self.superviseur, self.eleve_scope, entreprise)
        self.assertEqual(response.status_code, 302)
        prospection = Prospection.objects.get(eleve=self.eleve_scope, entreprise=entreprise)
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.ACTION_STAFF_ELEVE,
            cible_id=str(prospection.pk),
            details__proprietaire_id=self.eleve_scope.pk,
        ).exists())
        self.assertFalse(Notification.objects.filter(
            destinataire=self.eleve_scope,
            type=TypeNotification.AJOUT_PROSPECTION,
        ).exists())

    def test_superviseur_ne_peut_pas_creer_pour_un_eleve_hors_scope(self):
        entreprise = Entreprise.objects.create(nom="Création hors scope")
        response = self.poster_creation(self.superviseur, self.eleve_hors_scope, entreprise)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Prospection.objects.filter(eleve=self.eleve_hors_scope, entreprise=entreprise).exists())

    def test_admin_cree_pour_lui_meme_sans_notification_staff(self):
        entreprise = Entreprise.objects.create(nom="Création admin pour soi")
        response = self.poster_creation(self.admin, self.admin, entreprise)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Prospection.objects.filter(eleve=self.admin, entreprise=entreprise).exists())
        self.assertFalse(JournalAction.objects.filter(
            action=JournalAction.Action.ACTION_STAFF_ELEVE,
        ).exists())

    def test_admin_cree_pour_un_eleve_et_un_superviseur(self):
        entreprise_eleve = Entreprise.objects.create(nom="Création admin pour élève")
        entreprise_superviseur = Entreprise.objects.create(nom="Création admin pour superviseur")
        response_eleve = self.poster_creation(self.admin, self.eleve, entreprise_eleve)
        self.assertEqual(response_eleve.status_code, 302)
        response_superviseur = self.poster_creation(self.admin, self.autre_superviseur, entreprise_superviseur)
        self.assertEqual(response_superviseur.status_code, 302)
        self.assertTrue(Prospection.objects.filter(eleve=self.eleve, entreprise=entreprise_eleve).exists())
        self.assertTrue(Prospection.objects.filter(eleve=self.autre_superviseur, entreprise=entreprise_superviseur).exists())
        self.assertEqual(
            JournalAction.objects.filter(action=JournalAction.Action.ACTION_STAFF_ELEVE).count(),
            2,
        )
        self.assertFalse(Notification.objects.filter(
            destinataire=self.autre_superviseur,
            type=TypeNotification.AJOUT_PROSPECTION,
        ).exists())


    def test_mode_mine_superviseur_affiche_uniquement_ses_prospections(self):
        propre = self.creer_prospection(self.superviseur, "Mine superviseur")
        self.creer_prospection(self.eleve_scope, "Élève du scope")
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("entreprises:prospections_toutes"), {"mine": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["prospections"]), [propre])
        self.assertEqual(response.context["titre_prospections"], "Mes prospections")

    def test_mode_eleves_superviseur_limite_aux_eleves_de_son_scope(self):
        dans_scope = self.creer_prospection(self.eleve_scope, "Élève du scope ciblé")
        self.creer_prospection(self.eleve_hors_scope, "Élève hors scope ciblé")
        self.creer_prospection(self.superviseur, "Superviseur ciblé")
        self.client.force_login(self.superviseur)
        response = self.client.get(
            reverse("entreprises:prospections_toutes"),
            {"eleves": "1", "statut": Statut.A_CONTACTER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["prospections"]), [dans_scope])
        self.assertEqual(response.context["titre_prospections"], "Prospections des élèves")

    def test_mode_superviseurs_refuse_a_un_superviseur(self):
        self.client.force_login(self.superviseur)
        response = self.client.get(
            reverse("entreprises:prospections_toutes"),
            {"superviseurs": "1"},
        )
        self.assertEqual(response.status_code, 403)

    def test_mode_mine_admin_affiche_uniquement_ses_prospections(self):
        propre = self.creer_prospection(self.admin, "Mine admin")
        self.creer_prospection(self.eleve, "Élève hors mine admin")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("entreprises:prospections_toutes"), {"mine": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["prospections"]), [propre])
        self.assertEqual(response.context["titre_prospections"], "Mes prospections")

    def test_mode_eleves_admin_affiche_uniquement_les_eleves(self):
        eleve = self.creer_prospection(self.eleve, "Élève admin")
        self.creer_prospection(self.superviseur, "Superviseur exclu admin")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("entreprises:prospections_toutes"), {"eleves": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["prospections"]), [eleve])
        self.assertEqual(response.context["titre_prospections"], "Prospections des élèves")

    def test_mode_superviseurs_admin_affiche_uniquement_les_superviseurs(self):
        superviseur = self.creer_prospection(self.superviseur, "Prospection superviseur admin")
        self.creer_prospection(self.eleve, "Élève exclu superviseur admin")
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("entreprises:prospections_toutes"),
            {"superviseurs": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["prospections"]), [superviseur])
        self.assertEqual(response.context["titre_prospections"], "Prospections des superviseurs")

    def test_priorite_mine_sur_eleves_et_superviseurs(self):
        propre = self.creer_prospection(self.admin, "Priorité mine")
        self.creer_prospection(self.eleve, "Élève hors mode prioritaire")
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("entreprises:prospections_toutes"),
            {"mine": "1", "eleves": "1", "superviseurs": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["prospections"]), [propre])
        self.assertEqual(response.context["titre_prospections"], "Mes prospections")

    def test_le_formulaire_conserve_le_segment_actif(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("entreprises:prospections_toutes"),
            {"eleves": "1"},
        )
        self.assertContains(response, 'name="eleves" value="1"')

    def test_superviseur_peut_lire_une_prospection_dans_son_scope(self):
        prospection = self.creer_prospection(self.eleve_scope, "Détail dans le scope")
        self.client.force_login(self.superviseur)

        response = self.client.get(reverse("entreprises:detail", args=[prospection.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Détail dans le scope")
        self.assertNotContains(response, ">Modifier</a>")
        self.assertNotContains(response, ">Supprimer</a>")
        self.assertContains(response, ">Changer de statut</a>")

    def test_superviseur_peut_modifier_sa_propre_prospection(self):
        prospection = self.creer_prospection(self.superviseur, "Modification propre superviseur")
        self.client.force_login(self.superviseur)

        response = self.client.post(
            reverse("entreprises:update", args=[prospection.pk]),
            {
                "statut": Statut.A_CONTACTER,
                "type_contrat": TypeContrat.STAGE,
                "notes": "Notes du superviseur",
                "source": "Salon",
                "entreprise_nom": prospection.entreprise.nom,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("entreprises:detail", args=[prospection.pk]))
        prospection.refresh_from_db()
        self.assertEqual(prospection.notes, "Notes du superviseur")

    def test_superviseur_peut_supprimer_sa_propre_prospection(self):
        prospection = self.creer_prospection(self.superviseur, "Suppression propre superviseur")
        self.client.force_login(self.superviseur)

        response = self.client.post(reverse("entreprises:delete", args=[prospection.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("entreprises:prospections_toutes"))
        self.assertFalse(Prospection.objects.filter(pk=prospection.pk).exists())

    def test_superviseur_ne_peut_pas_modifier_prospection_eleve_scope(self):
        prospection = self.creer_prospection(self.eleve_scope, "Modification interdite scope")
        self.client.force_login(self.superviseur)

        response = self.client.get(reverse("entreprises:update", args=[prospection.pk]))

        self.assertEqual(response.status_code, 403)

    def test_superviseur_ne_peut_pas_supprimer_prospection_eleve_scope(self):
        prospection = self.creer_prospection(self.eleve_scope, "Suppression interdite scope")
        self.client.force_login(self.superviseur)

        response = self.client.post(reverse("entreprises:delete", args=[prospection.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Prospection.objects.filter(pk=prospection.pk).exists())

    def test_superviseur_peut_changer_statut_dans_scope(self):
        prospection = self.creer_prospection(self.eleve_scope, "Statut dans scope")
        self.client.force_login(self.superviseur)

        response = self.client.post(
            reverse("entreprises:changer_statut", args=[prospection.pk]),
            {"nouveau_statut": Statut.REFUS, "commentaire": "Décision reçue"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("entreprises:detail", args=[prospection.pk]))
        prospection.refresh_from_db()
        self.assertEqual(prospection.statut, Statut.REFUS)
        historique = HistoriqueStatut.objects.get(prospection=prospection)
        self.assertEqual(historique.auteur, self.superviseur)
        self.assertTrue(JournalAction.objects.filter(
            utilisateur=self.superviseur,
            action=JournalAction.Action.CHANGEMENT_STATUT,
            cible_id=str(prospection.pk),
        ).exists())

    def test_admin_peut_modifier_prospection(self):
        prospection = self.creer_prospection(self.eleve, "Modification admin")
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("entreprises:update", args=[prospection.pk]),
            {
                "statut": Statut.REFUS,
                "type_contrat": TypeContrat.STAGE,
                "notes": "Modifiée par admin",
                "source": "Admin",
                "entreprise_nom": prospection.entreprise.nom,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("entreprises:detail", args=[prospection.pk]))
        prospection.refresh_from_db()
        self.assertEqual(prospection.notes, "Modifiée par admin")
        historique = HistoriqueStatut.objects.get(prospection=prospection)
        self.assertEqual(historique.auteur, self.admin)
        self.assertTrue(JournalAction.objects.filter(
            utilisateur=self.admin,
            action=JournalAction.Action.CHANGEMENT_STATUT,
            cible_id=str(prospection.pk),
        ).exists())

    def test_admin_peut_supprimer_prospection(self):
        prospection = self.creer_prospection(self.eleve, "Suppression admin")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("entreprises:delete", args=[prospection.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("entreprises:prospections_toutes"))
        self.assertFalse(Prospection.objects.filter(pk=prospection.pk).exists())
