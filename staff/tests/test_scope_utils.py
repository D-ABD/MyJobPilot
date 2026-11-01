"""Tests des helpers d'isolation des superviseurs."""
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from comptes.models import Centre, Formation, ScopeSuperviseur, Utilisateur
from comptes.scope_utils import centres_du_superviseur, superviser_eleve, verifier_superviseur


class ScopeUtilsTests(TestCase):
    def setUp(self):
        self.centre_a = Centre.objects.create(nom="Centre scope A", departement="75 - Paris")
        self.centre_b = Centre.objects.create(nom="Centre scope B", departement="69 - Rhône")
        self.formation_a = Formation.objects.create(centre=self.centre_a, nom="Formation A")
        self.formation_b = Formation.objects.create(centre=self.centre_b, nom="Formation B")
        self.superviseur = self.creer_superviseur("superviseur_scope", self.centre_a)
        self.eleve_a = self.creer_eleve("eleve_scope_a", self.centre_a, self.formation_a)
        self.eleve_b = self.creer_eleve("eleve_scope_b", self.centre_b, self.formation_b)
        self.factory = RequestFactory()

    def creer_superviseur(self, username, centre):
        return Utilisateur.objects.create_user(
            username=username,
            password=None,
            role=Utilisateur.Role.SUPERVISEUR,
            centre=centre,
            is_staff=True,
            is_valide=True,
        )

    def creer_eleve(self, username, centre, formation):
        return Utilisateur.objects.create_user(
            username=username,
            password=None,
            role=Utilisateur.Role.ELEVE,
            centre=centre,
            formation=formation,
            is_valide=True,
        )

    def requete(self, utilisateur):
        request = self.factory.get("/")
        request.user = utilisateur
        return request

    def test_centres_du_superviseur_retourne_scope_actif(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        self.assertEqual(centres_du_superviseur(self.superviseur), [self.centre_a.pk])

    def test_centres_du_superviseur_retourne_union_des_scopes(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_b)
        self.assertCountEqual(
            centres_du_superviseur(self.superviseur),
            [self.centre_a.pk, self.centre_b.pk],
        )

    def test_centres_du_superviseur_sans_scope_retourne_liste_vide(self):
        self.assertEqual(centres_du_superviseur(self.superviseur), [])

    def test_centres_du_superviseur_refuse_admin(self):
        admin = Utilisateur.objects.create_superuser(
            username="admin_scope", email="admin@example.com", password="mot-de-passe"
        )
        self.assertEqual(centres_du_superviseur(admin), [])

    def test_centres_du_superviseur_refuse_eleve(self):
        self.assertEqual(centres_du_superviseur(self.eleve_a), [])

    def test_centres_du_superviseur_refuse_utilisateur_anonyme(self):
        self.assertEqual(centres_du_superviseur(None), [])

    def test_superviser_eleve_accepte_un_eleve_dans_le_scope(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        self.assertTrue(superviser_eleve(self.superviseur, self.eleve_a))

    def test_superviser_eleve_refuse_un_eleve_hors_scope(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        self.assertFalse(superviser_eleve(self.superviseur, self.eleve_b))

    def test_superviser_eleve_refuse_une_cible_admin(self):
        admin = Utilisateur.objects.create_superuser(
            username="admin_cible", email="cible@example.com", password="mot-de-passe"
        )
        self.assertFalse(superviser_eleve(self.superviseur, admin))

    def test_superviser_eleve_refuse_eleve_sans_centre(self):
        eleve = Utilisateur.objects.create_user(
            username="eleve_sans_centre",
            password=None,
            role=Utilisateur.Role.ELEVE,
            is_valide=True,
        )
        self.assertFalse(superviser_eleve(self.superviseur, eleve))

    def test_superviser_eleve_refuse_scope_inactif(self):
        scope = ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        scope.desactiver(auteur=self.superviseur)
        self.assertFalse(superviser_eleve(self.superviseur, self.eleve_a))

    def test_verifier_superviseur_refuse_eleve(self):
        with self.assertRaises(PermissionDenied):
            verifier_superviseur(self.requete(self.eleve_a))

    def test_verifier_superviseur_refuse_admin(self):
        admin = Utilisateur.objects.create_superuser(
            username="admin_verification", email="verif@example.com", password="mot-de-passe"
        )
        with self.assertRaises(PermissionDenied):
            verifier_superviseur(self.requete(admin))

    def test_verifier_superviseur_accepte_superviseur_sans_scope(self):
        verifier_superviseur(self.requete(self.superviseur))
        self.assertEqual(centres_du_superviseur(self.superviseur), [])

    def test_verifier_superviseur_refuse_eleve_hors_scope(self):
        ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre_a)
        with self.assertRaises(PermissionDenied):
            verifier_superviseur(self.requete(self.superviseur), self.eleve_b)

    def test_verifier_superviseur_refuse_utilisateur_anonyme(self):
        request = self.factory.get("/")
        with self.assertRaises(PermissionDenied):
            verifier_superviseur(request)
