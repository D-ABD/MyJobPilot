"""Tests des permissions, de l'isolation et des actions de tâches."""
from django.test import TestCase, override_settings
from django.urls import reverse

from comptes.models import Centre, JournalAction, ScopeSuperviseur, Utilisateur
from core.models import Tache


@override_settings(SECURE_SSL_REDIRECT=False)
class TachesTests(TestCase):
    def setUp(self):
        self.paris, _ = Centre.objects.get_or_create(
            nom="Centre Paris", defaults={"departement": "75 - Paris"}
        )
        self.lyon, _ = Centre.objects.get_or_create(
            nom="Centre Taches Lyon", defaults={"departement": "69 - Rhône"}
        )
        self.eleve = Utilisateur.objects.create_user(
            username="tache_eleve", password="motdepasse", role=Utilisateur.Role.ELEVE,
            centre=self.paris, is_valide=True,
        )
        self.eleve_scope = Utilisateur.objects.create_user(
            username="tache_eleve_scope", password="motdepasse", role=Utilisateur.Role.ELEVE,
            centre=self.paris, is_valide=True,
        )
        self.eleve_hors_scope = Utilisateur.objects.create_user(
            username="tache_eleve_hors_scope", password="motdepasse", role=Utilisateur.Role.ELEVE,
            centre=self.lyon, is_valide=True,
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="tache_superviseur", password="motdepasse", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.paris, is_valide=True,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.paris)
        self.admin = Utilisateur.objects.create_superuser(
            username="tache_admin", email="tache-admin@example.com", password="motdepasse"
        )

    def creer_tache(self, titre, createur=None, assigne=None, statut=Tache.Statut.A_FAIRE):
        return Tache.objects.create(
            titre=titre,
            createur=createur or self.eleve,
            assigne_a=assigne or self.eleve,
            statut=statut,
        )

    def test_creation_tache_eleve(self):
        self.client.force_login(self.eleve)

        response = self.client.post(reverse("core:tache_nouvelle"), {
            "titre": "Envoyer une candidature",
            "description": "Préparer le dossier.",
            "date_echeance": "",
            "statut": Tache.Statut.A_FAIRE,
            "prospection": "",
            "assigne_a": self.eleve.pk,
        })

        self.assertRedirects(response, reverse("core:taches_liste"))
        tache = Tache.objects.get(titre="Envoyer une candidature")
        self.assertEqual(tache.createur, self.eleve)
        self.assertEqual(tache.assigne_a, self.eleve)
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.TACHE_CREE, cible_id=str(tache.pk),
        ).exists())

    def test_creation_tache_superviseur_pour_eleve_scope(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(reverse("core:tache_nouvelle"), {
            "titre": "Faire le point", "description": "", "date_echeance": "",
            "statut": Tache.Statut.A_FAIRE, "prospection": "",
            "assigne_a": self.eleve_scope.pk,
        })

        self.assertRedirects(response, reverse("core:taches_liste"))
        tache = Tache.objects.get(titre="Faire le point")
        self.assertEqual(tache.createur, self.superviseur)
        self.assertEqual(tache.assigne_a, self.eleve_scope)

    def test_creation_tache_superviseur_hors_scope(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(reverse("core:tache_nouvelle"), {
            "titre": "Hors scope", "description": "", "date_echeance": "",
            "statut": Tache.Statut.A_FAIRE, "prospection": "",
            "assigne_a": self.eleve_hors_scope.pk,
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Tache.objects.filter(titre="Hors scope").exists())

    def test_isolation_eleve(self):
        visible_assignee = self.creer_tache("Assignée à moi", createur=self.superviseur, assigne=self.eleve)
        visible_creatrice = self.creer_tache("Créée par moi", createur=self.eleve, assigne=self.eleve_scope)
        invisible = self.creer_tache("Tâche privée", createur=self.superviseur, assigne=self.eleve_scope)
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("core:taches_liste"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible_assignee.titre)
        self.assertContains(response, visible_creatrice.titre)
        self.assertNotContains(response, invisible.titre)

    def test_isolation_superviseur(self):
        propre = self.creer_tache("Tâche superviseur", createur=self.admin, assigne=self.superviseur)
        scope = self.creer_tache("Tâche élève du scope", createur=self.admin, assigne=self.eleve_scope)
        hors_scope = self.creer_tache("Tâche élève hors scope", createur=self.admin, assigne=self.eleve_hors_scope)
        self.client.force_login(self.superviseur)

        response = self.client.get(reverse("core:taches_liste"))

        self.assertContains(response, propre.titre)
        self.assertContains(response, scope.titre)
        self.assertNotContains(response, hors_scope.titre)

    def test_admin_voit_tout(self):
        tache_eleve = self.creer_tache("Visible admin élève", assigne=self.eleve)
        tache_hors_scope = self.creer_tache("Visible admin hors scope", assigne=self.eleve_hors_scope)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("core:taches_liste"))

        self.assertContains(response, tache_eleve.titre)
        self.assertContains(response, tache_hors_scope.titre)

    def test_assigne_peut_terminer_et_journalisation(self):
        tache = self.creer_tache("À terminer", createur=self.superviseur, assigne=self.eleve)
        self.client.force_login(self.eleve)

        response = self.client.post(reverse("core:tache_terminer", args=[tache.pk]))

        self.assertRedirects(response, reverse("core:taches_liste"))
        tache.refresh_from_db()
        self.assertEqual(tache.statut, Tache.Statut.TERMINEE)
        self.assertTrue(JournalAction.objects.filter(
            utilisateur=self.eleve,
            action=JournalAction.Action.TACHE_TERMINEE,
            cible_id=str(tache.pk),
        ).exists())

    def test_assigne_ne_peut_pas_modifier_ni_supprimer(self):
        tache = self.creer_tache("Créée par staff", createur=self.superviseur, assigne=self.eleve)
        self.client.force_login(self.eleve)

        modifier = self.client.get(reverse("core:tache_modifier", args=[tache.pk]))
        supprimer = self.client.post(reverse("core:tache_supprimer", args=[tache.pk]))

        self.assertEqual(modifier.status_code, 403)
        self.assertEqual(supprimer.status_code, 403)
        self.assertTrue(Tache.objects.filter(pk=tache.pk).exists())

    def test_supprimer_tache_par_createur_journalise_avant_suppression(self):
        tache = self.creer_tache("À supprimer", createur=self.eleve, assigne=self.eleve)
        self.client.force_login(self.eleve)

        response = self.client.post(reverse("core:tache_supprimer", args=[tache.pk]))

        self.assertRedirects(response, reverse("core:taches_liste"))
        self.assertFalse(Tache.objects.filter(pk=tache.pk).exists())
        self.assertTrue(JournalAction.objects.filter(
            utilisateur=self.eleve,
            action=JournalAction.Action.TACHE_SUPPRIMEE,
            cible_id=str(tache.pk),
        ).exists())

    def test_compteur_retourne_les_taches_a_faire_visibles(self):
        self.creer_tache("À faire assignée", createur=self.superviseur, assigne=self.eleve)
        self.creer_tache("En cours", createur=self.eleve, assigne=self.eleve, statut=Tache.Statut.EN_COURS)
        self.creer_tache("Hors visibilité", createur=self.superviseur, assigne=self.eleve_scope)
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("core:taches_compteur"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 1})

    def test_modification_reservee_au_createur(self):
        tache = self.creer_tache("Titre avant", createur=self.eleve, assigne=self.eleve)
        self.client.force_login(self.eleve)

        response = self.client.post(reverse("core:tache_modifier", args=[tache.pk]), {
            "titre": "Titre après", "description": "", "date_echeance": "",
            "statut": Tache.Statut.EN_COURS, "prospection": "", "assigne_a": self.eleve.pk,
        })

        self.assertRedirects(response, reverse("core:taches_liste"))
        tache.refresh_from_db()
        self.assertEqual(tache.titre, "Titre après")

