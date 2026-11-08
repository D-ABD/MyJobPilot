from django.test import TestCase
from django.urls import reverse


class NavigationTests(TestCase):
    def test_lien_offres_alternance_present_dans_base(self):
        response = self.client.get(reverse("comptes:accueil"))

        self.assertEqual(response.status_code, 200)
        lien = f'href="{reverse("core:offres_alternance")}"'
        contenu = response.content.decode()
        self.assertEqual(contenu.count(lien), 2)
        self.assertEqual(contenu.count("Offres d'alternance"), 2)
