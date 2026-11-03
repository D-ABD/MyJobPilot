from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from comptes.models import JournalAction, Utilisateur


class PurgeJournalTests(TestCase):
    def test_dry_run_conserve_anciennes_entrees(self):
        user = Utilisateur.objects.create_user(username="journal_user", password="p")
        row = JournalAction.objects.create(utilisateur=user, action=JournalAction.Action.LOGIN)
        JournalAction.objects.filter(pk=row.pk).update(date=timezone.now() - timedelta(days=1100))
        call_command("purge_journal", dry_run=True, verbosity=0)
        self.assertTrue(JournalAction.objects.filter(pk=row.pk).exists())

    def test_purge_supprime_anciennes_entrees(self):
        user = Utilisateur.objects.create_user(username="journal_user2", password="p")
        row = JournalAction.objects.create(utilisateur=user, action=JournalAction.Action.LOGIN)
        JournalAction.objects.filter(pk=row.pk).update(date=timezone.now() - timedelta(days=1100))
        call_command("purge_journal", verbosity=0)
        self.assertFalse(JournalAction.objects.filter(pk=row.pk).exists())
