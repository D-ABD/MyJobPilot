from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Centre, Formation, JournalAction, ScopeSuperviseur, Utilisateur
from core.models import Objectif
from core.stats import calculer_atteinte_objectif
from entreprises.models import Entreprise, Prospection, Statut


class ObjectifsTests(TestCase):
    def setUp(self):
        self.centre_a = Centre.objects.create(nom="Centre Objectifs A", departement="75")
        self.centre_b = Centre.objects.create(nom="Centre Objectifs B", departement="69")
        self.formation_a = Formation.objects.create(centre=self.centre_a, nom="Formation A")
        self.formation_b = Formation.objects.create(centre=self.centre_b, nom="Formation B")
        self.superviseur = Utilisateur.objects.create_user(
            username="sup_objectifs", password="p", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre_a, is_valide=True,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        self.eleve = self.creer_eleve("eleve_objectifs", self.centre_a, self.formation_a)
        self.autre_eleve = self.creer_eleve("eleve_hors_scope", self.centre_b, self.formation_b)
        self.admin = Utilisateur.objects.create_superuser(
            username="admin_objectifs", email="admin-objectifs@example.com", password="p",
        )
        self.debut = timezone.localdate() - timedelta(days=6)
        self.fin = timezone.localdate() + timedelta(days=24)

    def creer_eleve(self, username, centre, formation):
        return Utilisateur.objects.create_user(
            username=username, password="p", role=Utilisateur.Role.ELEVE,
            centre=centre, formation=formation, is_valide=True,
        )

    def creer_objectif(self, eleve=None, createur=None, type_objectif=Objectif.Type.PROSPECTIONS_SEMAINE,
                       valeur=4, debut=None, fin=None):
        return Objectif.objects.create(
            createur=createur or self.superviseur,
            eleve=eleve or self.eleve,
            type=type_objectif,
            valeur=valeur,
            periode_debut=debut or self.debut,
            periode_fin=fin or self.fin,
        )

    def donnees_formulaire(self, eleve=None, type_objectif=Objectif.Type.PROSPECTIONS_SEMAINE):
        return {
            "eleve": (eleve or self.eleve).pk,
            "type": type_objectif,
            "valeur": 4,
            "periode_debut": self.debut.isoformat(),
            "periode_fin": self.fin.isoformat(),
        }

    def creer_prospection(self, eleve, index, statut=Statut.A_CONTACTER, date_candidature=None):
        return Prospection.objects.create(
            eleve=eleve,
            entreprise=Entreprise.objects.create(nom=f"Entreprise objectif {index}"),
            statut=statut,
            date_candidature=date_candidature,
        )

    def test_superviseur_peut_creer_objectif_pour_eleve_scope(self):
        self.client.force_login(self.superviseur)
        response = self.client.post(reverse("objectifs:nouveau"), self.donnees_formulaire())
        self.assertRedirects(response, reverse("objectifs:liste"))
        self.assertTrue(Objectif.objects.filter(eleve=self.eleve, createur=self.superviseur).exists())

    def test_superviseur_ne_peut_pas_creer_objectif_hors_scope(self):
        self.client.force_login(self.superviseur)
        response = self.client.post(reverse("objectifs:nouveau"), self.donnees_formulaire(self.autre_eleve))
        self.assertEqual(response.status_code, 403)

    def test_admin_peut_creer_objectif_pour_tout_eleve(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("objectifs:nouveau"), self.donnees_formulaire(self.autre_eleve))
        self.assertRedirects(response, reverse("objectifs:liste"))
        self.assertTrue(Objectif.objects.filter(eleve=self.autre_eleve, createur=self.admin).exists())

    def test_admin_peut_modifier_tout_objectif(self):
        objectif = self.creer_objectif(eleve=self.autre_eleve)
        self.client.force_login(self.admin)
        donnees = self.donnees_formulaire(self.autre_eleve)
        donnees["valeur"] = 8
        response = self.client.post(reverse("objectifs:modifier", args=[objectif.pk]), donnees)
        self.assertRedirects(response, reverse("objectifs:liste"))
        objectif.refresh_from_db()
        self.assertEqual(objectif.valeur, 8)

    def test_admin_peut_supprimer_tout_objectif(self):
        objectif = self.creer_objectif(eleve=self.autre_eleve)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("objectifs:supprimer", args=[objectif.pk]))
        self.assertRedirects(response, reverse("objectifs:liste"))
        self.assertFalse(Objectif.objects.filter(pk=objectif.pk).exists())

    def test_superviseur_peut_modifier_objectif_scope(self):
        objectif = self.creer_objectif()
        self.client.force_login(self.superviseur)
        donnees = self.donnees_formulaire()
        donnees["valeur"] = 9
        response = self.client.post(reverse("objectifs:modifier", args=[objectif.pk]), donnees)
        self.assertRedirects(response, reverse("objectifs:liste"))
        objectif.refresh_from_db()
        self.assertEqual(objectif.valeur, 9)

    def test_superviseur_peut_supprimer_objectif_scope(self):
        objectif = self.creer_objectif()
        self.client.force_login(self.superviseur)
        response = self.client.post(reverse("objectifs:supprimer", args=[objectif.pk]))
        self.assertRedirects(response, reverse("objectifs:liste"))
        self.assertFalse(Objectif.objects.filter(pk=objectif.pk).exists())

    def test_eleve_peut_voir_ses_objectifs(self):
        objectif = self.creer_objectif()
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("objectifs:liste"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(objectif.valeur))
        self.assertFalse(response.context["peut_gerer"])

    def test_eleve_ne_peut_pas_creer_objectif(self):
        self.client.force_login(self.eleve)
        response = self.client.post(reverse("objectifs:nouveau"), self.donnees_formulaire())
        self.assertEqual(response.status_code, 403)

    def test_eleve_ne_peut_pas_voir_objectifs_autre_eleve(self):
        objectif = self.creer_objectif(eleve=self.autre_eleve)
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("objectifs:modifier", args=[objectif.pk]))
        self.assertEqual(response.status_code, 404)

    def test_calcul_atteinte_prospections_semaine(self):
        objectif = self.creer_objectif(valeur=2, debut=timezone.localdate() - timedelta(days=13),
                                       fin=timezone.localdate())
        for index in range(4):
            self.creer_prospection(self.eleve, index)
        resultat = calculer_atteinte_objectif(objectif)
        self.assertEqual(resultat["valeur_actuelle"], 2)
        self.assertEqual(resultat["pourcentage"], 100)
        self.assertEqual(resultat["statut"], "atteint")

    def test_calcul_atteinte_candidatures_mois(self):
        objectif = self.creer_objectif(type_objectif=Objectif.Type.CANDIDATURES_MOIS, valeur=2)
        self.creer_prospection(self.eleve, "candidature 1", Statut.CANDIDATURE_ENVOYEE, timezone.localdate())
        self.creer_prospection(self.eleve, "candidature 2", Statut.CANDIDATURE_ENVOYEE, timezone.localdate())
        self.creer_prospection(self.eleve, "sans candidature", Statut.A_CONTACTER)
        Prospection.objects.filter(entreprise__nom="Entreprise objectif candidature 1").update(
            date_creation=timezone.now() - timedelta(days=90)
        )
        resultat = calculer_atteinte_objectif(objectif)
        self.assertEqual(resultat["valeur_actuelle"], 2)
        self.assertEqual(resultat["pourcentage"], 100)

    def test_calcul_atteinte_100_pourcent(self):
        objectif = self.creer_objectif(valeur=1, debut=timezone.localdate(), fin=timezone.localdate())
        self.creer_prospection(self.eleve, "objectif atteint")
        self.assertEqual(calculer_atteinte_objectif(objectif)["pourcentage"], 100)

    def test_calcul_atteinte_0_pourcent(self):
        objectif = self.creer_objectif(debut=timezone.localdate(), fin=timezone.localdate())
        resultat = calculer_atteinte_objectif(objectif)
        self.assertEqual(resultat["pourcentage"], 0)
        self.assertEqual(resultat["statut"], "en_retard")

    def test_eleve_sans_objectif_candidatures_non_penalise(self):
        self.creer_objectif(type_objectif=Objectif.Type.PROSPECTIONS_SEMAINE)
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("objectifs:liste"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Objectifs")
        self.assertEqual(len(response.context["objectifs"]), 1)

    def test_dashboard_superviseur_affiche_objectifs(self):
        self.creer_objectif()
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("staff:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Objectifs")
        self.assertEqual(len(response.context["objectifs_actifs"]), 1)

    def test_dashboard_admin_affiche_objectifs(self):
        self.creer_objectif()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["objectifs_actifs"]), 1)

    def test_dashboard_met_en_evidence_objectifs_non_atteints(self):
        self.creer_objectif()
        self.client.force_login(self.superviseur)
        response = self.client.get(reverse("staff:dashboard"))
        self.assertContains(response, "En retard")
        self.assertContains(response, "text-bg-danger")

    def test_unique_objectif_par_eleve_type_periode(self):
        self.creer_objectif()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.creer_objectif()

    def test_creation_objectif_journalise(self):
        self.client.force_login(self.superviseur)
        self.client.post(reverse("objectifs:nouveau"), self.donnees_formulaire())
        action = JournalAction.objects.get(action=JournalAction.Action.OBJECTIF_CREE)
        objectif = Objectif.objects.get(eleve=self.eleve)
        self.assertEqual(action.details, {"objectif_id": objectif.pk, "eleve_id": self.eleve.pk,
                                          "type": Objectif.Type.PROSPECTIONS_SEMAINE})

    def test_modification_objectif_journalise(self):
        objectif = self.creer_objectif()
        self.client.force_login(self.superviseur)
        donnees = self.donnees_formulaire()
        donnees["valeur"] = 11
        self.client.post(reverse("objectifs:modifier", args=[objectif.pk]), donnees)
        action = JournalAction.objects.get(action=JournalAction.Action.OBJECTIF_MODIFIE)
        self.assertEqual(action.details["objectif_id"], objectif.pk)
        self.assertEqual(action.details["eleve_id"], self.eleve.pk)
        self.assertEqual(action.details["type"], objectif.type)

    def test_suppression_objectif_journalise(self):
        objectif = self.creer_objectif()
        self.client.force_login(self.superviseur)
        self.client.post(reverse("objectifs:supprimer", args=[objectif.pk]))
        action = JournalAction.objects.get(action=JournalAction.Action.OBJECTIF_SUPPRIME)
        self.assertEqual(action.details["objectif_id"], objectif.pk)
        self.assertEqual(action.details["eleve_id"], self.eleve.pk)
        self.assertEqual(action.details["type"], objectif.type)

    def test_periode_invalide_est_refusee(self):
        self.client.force_login(self.admin)
        donnees = self.donnees_formulaire()
        donnees["periode_fin"] = self.debut.isoformat()
        response = self.client.post(reverse("objectifs:nouveau"), donnees)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Objectif.objects.exists())
