from django.test import TestCase
from django.urls import reverse

from comptes.models import Centre, ScopeSuperviseur, Utilisateur


class ModificationCodesRomeTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(
            nom="Centre codes scope",
            defaults={"departement": "75 - Paris"},
        )
        self.hors_scope, _ = Centre.objects.get_or_create(
            nom="Centre codes hors scope",
            defaults={"departement": "69 - Rhône"},
        )
        self.superviseur = Utilisateur.objects.create_user(
            username="superviseur_codes", password="test", role=Utilisateur.Role.SUPERVISEUR,
            centre=self.centre, is_valide=True,
        )
        self.eleve_scope = Utilisateur.objects.create_user(
            username="eleve_codes_scope", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.centre, is_valide=True,
        )
        self.eleve_hors_scope = Utilisateur.objects.create_user(
            username="eleve_codes_hors", password="test", role=Utilisateur.Role.ELEVE,
            centre=self.hors_scope, is_valide=True,
        )
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre)

    def test_superviseur_peut_modifier_codes_rome_eleve_dans_scope(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(reverse("staff:modifier_codes_rome", args=[self.eleve_scope.pk]), {
            "codes_rome": "M1805,I1401",
        })

        self.assertRedirects(response, reverse("staff:detail_eleve", args=[self.eleve_scope.pk]))
        self.eleve_scope.refresh_from_db()
        self.assertEqual(self.eleve_scope.codes_rome, "M1805,I1401")

    def test_superviseur_ne_peut_pas_modifier_codes_rome_hors_scope(self):
        self.client.force_login(self.superviseur)

        response = self.client.post(reverse("staff:modifier_codes_rome", args=[self.eleve_hors_scope.pk]), {
            "codes_rome": "M1805",
        })

        self.assertEqual(response.status_code, 403)
        self.eleve_hors_scope.refresh_from_db()
        self.assertEqual(self.eleve_hors_scope.codes_rome, "")
