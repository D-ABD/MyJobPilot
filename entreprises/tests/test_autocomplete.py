"""Tests de l'autocomplete du référentiel public d'entreprises."""
from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, Formation, Utilisateur
from entreprises.models import Entreprise, Prospection, Statut


class RechercheEntreprisesTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre Paris",
            defaults={"departement": "75 - Paris"},
        )
        self.formation, _ = Formation.objects.get_or_create(centre=self.centre, nom="BTS SIO")
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_autocomplete",
            password="mot-de-passe",
            role=Utilisateur.Role.ELEVE,
            centre=self.centre,
            formation=self.formation,
            is_valide=True,
        )

    def test_recherche_est_refusee_sans_authentification(self):
        response = self.client.get(reverse("entreprises:search"), {"q": "Acme"})
        self.assertEqual(response.status_code, 302)

    def test_recherche_retourne_uniquement_id_nom_et_ville(self):
        entreprise = Entreprise.objects.create(nom="ACME Corp", ville="Paris")
        Prospection.objects.create(
            eleve=self.eleve,
            entreprise=entreprise,
            statut=Statut.REFUS,
            notes="Information privée de l'élève",
        )
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:search"), {"q": "acme"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), [{"id": entreprise.pk, "nom": "ACME Corp", "ville": "Paris"}])

    def test_recherche_limite_les_resultats_a_dix(self):
        for numero in range(12):
            Entreprise.objects.create(nom=f"Acme {numero:02d}", ville="Paris")
        self.client.force_login(self.eleve)

        response = self.client.get(reverse("entreprises:search"), {"q": "Acme"})

        self.assertEqual(len(response.json()), 10)

    def test_recherche_vide_ne_retourne_aucun_referentiel(self):
        Entreprise.objects.create(nom="ACME Corp")
        self.client.force_login(self.eleve)
        response = self.client.get(reverse("entreprises:search"), {"q": "  "})
        self.assertEqual(response.json(), [])
