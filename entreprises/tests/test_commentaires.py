from django.test import TestCase
from django.urls import reverse

from comptes.models import (
    Centre,
    Formation,
    JournalAction,
    Notification,
    ScopeSuperviseur,
    TypeNotification,
    Utilisateur,
)
from entreprises.models import Commentaire, Entreprise, Prospection


class CommentaireTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.autre_centre, _ = Centre.objects.get_or_create(
            nom="Centre Lyon",
            defaults={"departement": "69 - Rhône"},
        )
        self.formation, _ = Formation.objects.get_or_create(
            centre=self.centre,
            nom="BTS SIO",
        )
        self.autre_formation, _ = Formation.objects.get_or_create(
            centre=self.autre_centre,
            nom="BTS SIO",
        )
        self.eleve = self.creer_utilisateur(
            "commentaire_eleve",
            Utilisateur.Role.ELEVE,
            self.centre,
            self.formation,
        )
        self.autre_eleve = self.creer_utilisateur(
            "commentaire_autre",
            Utilisateur.Role.ELEVE,
            self.autre_centre,
            self.autre_formation,
        )
        self.superviseur = self.creer_utilisateur(
            "commentaire_superviseur",
            Utilisateur.Role.SUPERVISEUR,
            self.centre,
            self.formation,
        )
        self.admin = self.creer_utilisateur(
            "commentaire_admin",
            Utilisateur.Role.ADMIN,
            self.centre,
            self.formation,
            is_staff=True,
            is_superuser=True,
        )
        self.entreprise = Entreprise.objects.create(nom="Entreprise commentaire")
        self.prospection = Prospection.objects.create(
            eleve=self.eleve,
            entreprise=self.entreprise,
        )

    def creer_utilisateur(self, username, role, centre, formation, **extra):
        return Utilisateur.objects.create_user(
            username=username,
            password="test-password",
            role=role,
            centre=centre,
            formation=formation,
            is_valide=True,
            **extra,
        )

    def ajouter_scope(self, superviseur=None, centre=None, actif=True):
        return ScopeSuperviseur.objects.create(
            superviseur=superviseur or self.superviseur,
            centre=centre or self.centre,
            is_active=actif,
        )

    def creer_commentaire(self, auteur=None):
        return Commentaire.objects.create(
            auteur=auteur or self.eleve,
            prospection=self.prospection,
            contenu="Échange au sujet de la candidature.",
        )

    def test_commentaire_est_lie_a_la_prospection_et_auteur(self):
        commentaire = self.creer_commentaire()
        self.assertEqual(commentaire.prospection, self.prospection)
        self.assertEqual(commentaire.auteur, self.eleve)

    def test_eleve_cree_commentaire_et_notifie_tous_les_superviseurs_actifs(self):
        second = self.creer_utilisateur(
            "commentaire_superviseur_2",
            Utilisateur.Role.SUPERVISEUR,
            self.centre,
            self.formation,
        )
        inactif = self.creer_utilisateur(
            "commentaire_superviseur_inactif",
            Utilisateur.Role.SUPERVISEUR,
            self.centre,
            self.formation,
        )
        self.ajouter_scope(self.superviseur)
        self.ajouter_scope(second)
        self.ajouter_scope(inactif)
        inactif.is_active = False
        inactif.save(update_fields=["is_active"])
        self.client.force_login(self.eleve)

        response = self.client.post(
            reverse("entreprises:commentaire_ajouter", args=[self.prospection.pk]),
            {"contenu": "J'ai envoyé mon dossier."},
        )

        commentaire = Commentaire.objects.get(prospection=self.prospection)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(
                Notification.objects.filter(
                    type=TypeNotification.COMMENTAIRE
                ).values_list("destinataire_id", flat=True)
            ),
            {self.superviseur.pk, second.pk},
        )
        self.assertTrue(
            JournalAction.objects.filter(
                action=JournalAction.Action.COMMENTAIRE_CREE,
                cible_id=str(commentaire.pk),
            ).exists()
        )

    def test_eleve_sans_scope_actif_notifie_le_premier_admin_actif(self):
        self.client.force_login(self.eleve)
        self.client.post(
            reverse("entreprises:commentaire_ajouter", args=[self.prospection.pk]),
            {"contenu": "Question sur ma candidature."},
        )
        premier_admin = Utilisateur.objects.filter(
            role=Utilisateur.Role.ADMIN,
            is_active=True,
        ).first()
        self.assertEqual(
            list(Notification.objects.values_list("destinataire_id", flat=True)),
            [premier_admin.pk],
        )

    def test_commentaire_superviseur_notifie_eleve(self):
        self.ajouter_scope(self.superviseur)
        self.client.force_login(self.superviseur)
        response = self.client.post(
            reverse("entreprises:commentaire_ajouter", args=[self.prospection.pk]),
            {"contenu": "Je vous conseille de relancer l'entreprise."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Notification.objects.filter(
                destinataire=self.eleve,
                type=TypeNotification.COMMENTAIRE,
            ).exists()
        )

    def test_commentaire_admin_notifie_uniquement_eleve(self):
        self.ajouter_scope(self.superviseur)
        self.client.force_login(self.admin)
        self.client.post(
            reverse("entreprises:commentaire_ajouter", args=[self.prospection.pk]),
            {"contenu": "Votre dossier est complet."},
        )
        self.assertEqual(
            list(Notification.objects.values_list("destinataire_id", flat=True)),
            [self.eleve.pk],
        )

    def test_eleve_inactif_ne_recoit_pas_de_notification(self):
        self.ajouter_scope(self.superviseur)
        self.eleve.is_active = False
        self.eleve.save(update_fields=["is_active"])
        self.client.force_login(self.superviseur)
        self.client.post(
            reverse("entreprises:commentaire_ajouter", args=[self.prospection.pk]),
            {"contenu": "Retour superviseur."},
        )
        self.assertFalse(Notification.objects.exists())

    def test_eleve_ne_commente_pas_la_prospection_d_un_autre(self):
        autre_entreprise = Entreprise.objects.create(nom="Autre entreprise")
        autre_prospection = Prospection.objects.create(
            eleve=self.autre_eleve,
            entreprise=autre_entreprise,
        )
        self.client.force_login(self.eleve)
        response = self.client.post(
            reverse("entreprises:commentaire_ajouter", args=[autre_prospection.pk]),
            {"contenu": "Commentaire interdit."},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Commentaire.objects.exists())

    def test_superviseur_hors_scope_ne_commente_pas(self):
        self.client.force_login(self.superviseur)
        response = self.client.post(
            reverse("entreprises:commentaire_ajouter", args=[self.prospection.pk]),
            {"contenu": "Commentaire interdit."},
        )
        self.assertEqual(response.status_code, 403)

    def test_auteur_peut_supprimer_son_commentaire(self):
        commentaire = self.creer_commentaire()
        self.client.force_login(self.eleve)
        response = self.client.post(
            reverse("entreprises:commentaire_supprimer", args=[commentaire.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Commentaire.objects.filter(pk=commentaire.pk).exists())

    def test_admin_peut_supprimer_un_commentaire(self):
        commentaire = self.creer_commentaire()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("entreprises:commentaire_supprimer", args=[commentaire.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Commentaire.objects.filter(pk=commentaire.pk).exists())

    def test_un_autre_utilisateur_ne_peut_pas_supprimer_le_commentaire(self):
        commentaire = self.creer_commentaire()
        self.client.force_login(self.autre_eleve)
        response = self.client.post(
            reverse("entreprises:commentaire_supprimer", args=[commentaire.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Commentaire.objects.filter(pk=commentaire.pk).exists())
