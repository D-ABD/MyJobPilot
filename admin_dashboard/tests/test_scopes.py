from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from django.contrib.sessions.models import Session
from comptes.models import Centre, JournalAction, ScopeSuperviseur, Utilisateur


class AdminScopesTests(TestCase):
    def setUp(self):
        self.centre, _ = Centre.objects.get_or_create(nom="Centre Paris", defaults={"departement": "75 - Paris"})
        self.centre2, _ = Centre.objects.get_or_create(nom="Centre Lyon", defaults={"departement": "69 - Rhône"})
        self.admin = Utilisateur.objects.create_user(username="admin_scopes", password="p", role="admin", is_staff=True)
        self.superviseur = Utilisateur.objects.create_user(
            username="sup_scopes", password="p", role="superviseur",
            centre=self.centre, is_valide=True,
        )
        self.scope = ScopeSuperviseur.objects.create(superviseur=self.superviseur, centre=self.centre)

    def test_page_scopes_affiche_actifs_et_inactifs(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:superviseur_scopes", args=[self.superviseur.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)

    def test_ajout_scope_journalise(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_dashboard:scope_create", args=[self.superviseur.pk]), {
            "centre": self.centre2.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ScopeSuperviseur.objects.filter(superviseur=self.superviseur, centre=self.centre2, is_active=True).exists())
        self.assertTrue(JournalAction.objects.filter(action=JournalAction.Action.SCOPE_CREE, details__centre_id=self.centre2.pk).exists())

    def test_desactivation_scope_aware_et_journalisee(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_dashboard:scope_desactiver", args=[self.scope.pk]))
        self.assertEqual(response.status_code, 302)
        self.scope.refresh_from_db()
        self.assertFalse(self.scope.is_active)
        self.assertTrue(timezone.is_aware(self.scope.date_desactivation))
        self.assertTrue(JournalAction.objects.filter(
            action=JournalAction.Action.SCOPE_CREE,
            cible_id=str(self.scope.pk), details__action="desactivation",
        ).exists())

    def test_get_creation_scope_affiche_formulaire_dedie(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard:scope_create", args=[self.superviseur.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["afficher_formulaire"])

    def test_non_admin_ne_peut_pas_ajouter_scope(self):
        self.client.force_login(self.superviseur)
        response = self.client.post(reverse("admin_dashboard:scope_create", args=[self.superviseur.pk]), {"centre": self.centre2.pk})
        self.assertEqual(response.status_code, 403)


    def test_admin_superviseur_detail_accede(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse(
            "admin_dashboard:superviseur_detail", args=[self.superviseur.pk],
        ))
        self.assertEqual(response.status_code, 200)

    def test_admin_superviseur_modifier(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_dashboard:superviseur_modifier", args=[self.superviseur.pk]),
            {
                "username": "superviseur_renomme", "email": "sup-modifie@example.com",
                "first_name": "Sam", "last_name": "Superviseur",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.superviseur.refresh_from_db()
        self.assertEqual(self.superviseur.username, "superviseur_renomme")
        self.assertEqual(self.superviseur.email, "sup-modifie@example.com")

    def test_admin_superviseur_supprimer(self):
        client_superviseur = Client()
        client_superviseur.force_login(self.superviseur)
        session_key = client_superviseur.cookies["sessionid"].value
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_dashboard:superviseur_supprimer", args=[self.superviseur.pk]),
            {"confirmation": "oui"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Utilisateur.objects.filter(pk=self.superviseur.pk).exists())
        self.assertFalse(ScopeSuperviseur.objects.filter(pk=self.scope.pk).exists())
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
