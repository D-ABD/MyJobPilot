from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from comptes.models import Centre, Formation, Utilisateur


class PurgeRGPDTests(TestCase):
    def test_dry_run_ne_supprime_pas(self):
        user = Utilisateur.objects.create_user(username="ancien", password="p", is_active=False)
        Utilisateur.objects.filter(pk=user.pk).update(last_login=timezone.now() - timedelta(days=1100))
        call_command("purge_rgpd", dry_run=True, verbosity=0)
        self.assertTrue(Utilisateur.objects.filter(pk=user.pk).exists())

    def test_purge_compte_inactif_ancien(self):
        user = Utilisateur.objects.create_user(username="ancien2", password="p", is_active=False)
        Utilisateur.objects.filter(pk=user.pk).update(last_login=timezone.now() - timedelta(days=1100))
        call_command("purge_rgpd", verbosity=0)
        self.assertFalse(Utilisateur.objects.filter(pk=user.pk).exists())

    def test_purge_eleve_non_valide_ancien(self):
        centre, _ = Centre.objects.get_or_create(nom="Centre Paris", defaults={"departement": "75 - Paris"})
        formation, _ = Formation.objects.get_or_create(centre=centre, nom="BTS Test")
        user = Utilisateur.objects.create_user(username="attente_ancienne", password="p", role="eleve", centre=centre, formation=formation, is_valide=False)
        Utilisateur.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=190))
        call_command("purge_rgpd", verbosity=0)
        self.assertFalse(Utilisateur.objects.filter(pk=user.pk).exists())
