"""Tests des réglages spécifiques à l'exécution de la suite Django."""
from django.conf import settings
from django.test import SimpleTestCase


class SettingsTests(SimpleTestCase):
    def test_testing_flag_active_pendant_les_tests(self):
        self.assertIs(settings.TESTING, True)

    def test_secure_ssl_redirect_desactive_pendant_les_tests(self):
        self.assertIs(settings.SECURE_SSL_REDIRECT, False)
