# MyJobPilot — Lots 1 à 4

Application Django de prospection d'alternance. Le Lot 1 met en place la configuration, les comptes, l'inscription et la validation administrative. Le Lot 2 ajoute les entreprises, l'historique des statuts, les filtres et le dashboard élève.

## Prérequis

- Python 3.12
- pip
- PostgreSQL pour un déploiement en production

## Installation en développement

Depuis la racine du dépôt :

    python3.12 -m venv .venv
    source .venv/bin/activate
    test -f .env || cp .env.example .env
    pip install -r requirements.txt

La migration initiale des comptes et la migration des données de référence sont versionnées. Vérifiez la configuration puis appliquez-les :

    python manage.py check
    python manage.py migrate

    python manage.py creer_demo
    python manage.py runserver

La migration 0001_initial.py contient les modèles du socle, notamment le modèle utilisateur personnalisé et le consentement RGPD. La migration 0002_donnees_initiales.py ajoute les centres et formations de démonstration.

## Configuration

Les paramètres sont chargés depuis .env en développement ou depuis les variables de l'environnement en production :

- SECRET_KEY : clé Django, à remplacer avant tout déploiement.
- DEBUG : True en local dans le fichier d'exemple ; False par défaut si la variable est absente.
- ALLOWED_HOSTS : liste de noms d'hôte séparés par des virgules.
- DATABASE_URL : SQLite par défaut en développement ; URL PostgreSQL en production.

Quand DEBUG=False, la redirection HTTPS, les cookies sécurisés, HSTS et la protection de type MIME sont activés. Les limites prévues pour les documents sont disponibles dans les paramètres : 5 Mio par document et 20 Mio par élève. Elles seront appliquées avec le module Documents au Lot 5.

## Comptes de démonstration

La commande python manage.py creer_demo crée quatre comptes de manière idempotente :

| Rôle | Identifiant |
| --- | --- |
| Administrateur | admin_demo |
| Superviseur | superviseur_demo |
| Élève validé | eleve_demo |
| Élève en attente | eleve_attente_demo |

Les quatre comptes utilisent le mot de passe local défini par DEMO_PASSWORD dans votre fichier .env. Cette valeur ne doit pas être publiée ni utilisée en production. Si la variable n'est pas renseignée, la commande la demande de manière interactive au moment de créer les comptes. Le message de réussite affiche les identifiants, jamais le mot de passe.

L'administrateur valide, refuse ou désactive les comptes depuis l'administration Django à l'adresse /admin/. La désactivation invalide les sessions actives du compte.

## Consentement et sécurité

- Le consentement RGPD est recueilli à l'inscription (version 1.0) et traçable via le modèle ConsentementRGPD.
- Les élèves non validés sont redirigés vers /comptes/en-attente/ pour les vues protégées.
- Les actions d'authentification et les décisions administratives sont consignées dans JournalAction.
- Les erreurs 500 sont journalisées avec le chemin de la requête et l'identifiant du compte, sans contenu personnel.
- Pour les bases contenant beaucoup de sessions, une optimisation possible consiste à parcourir le queryset avec iterator(), collecter les clés à invalider par lots, puis supprimer chaque lot avec un delete groupé. Cette optimisation devra conserver la journalisation des sessions invalidées.

## Structure du projet

- myjobpilot/ : configuration et points d'entrée WSGI/ASGI.
- comptes/ : utilisateurs, centres, formations, consentement, authentification et journal.
- entreprises/ : prospections, statuts datés et historique du Lot 2.
- documents/ : app préparée pour le Lot 5.
- rgpd/ : app préparée pour le Lot 7.
- core/ : app commune, sans logique métier à ce lot.
- templates/ et static/css/custom.css : interface française Bootstrap.

## Lot 2 — Prospection élève

Les élèves validés peuvent créer, modifier, consulter et supprimer leurs propres entreprises depuis /dashboard/. Les changements de statut sont datés, attribués à leur auteur et conservés dans l'historique de chaque entreprise. Le dashboard propose des filtres combinables, un tri par colonne et une pagination de 25 lignes. La recherche du Lot 2 ignore la casse ; la normalisation des accents est reportée au Lot 8a.

Les tests du Lot 2 se lancent avec python manage.py test entreprises.tests. Les fichiers de migration de modèles sont générés localement avec makemigrations entreprises ; aucune migration de ce lot n'est versionnée ici.

## Lot 3 — Scopes et dashboard superviseur

Les superviseurs voient uniquement les élèves rattachés aux centres de leurs scopes actifs. Leur dashboard permet de rechercher un élève, de filtrer par centre et par état de validation, de trier par identifiant, nom, centre ou état de validation, et de parcourir les résultats par pages de 25. La fiche élève affiche ses informations et ses entreprises en lecture seule.

Les scopes peuvent être créés et désactivés depuis l'administration Django. Leur création est journalisée par `SCOPE_CREE` et leur désactivation par `ACCES_SCOPE_REFUSE`. Une désactivation conserve l'enregistrement du scope.

Les tests du Lot 3 se lancent avec `python manage.py test staff.tests comptes.tests` après génération locale des migrations du modèle `ScopeSuperviseur`.

## Lot 4 — Actions staff sur les élèves

Depuis la fiche staff d'un élève, un administrateur peut changer son centre ou lui ajouter une prospection. Un superviseur peut effectuer ces deux actions uniquement sur un élève de son scope actif ; le changement de centre est limité à ses centres de scope. Les changements de centre et ajouts de prospection sont inscrits dans JournalAction. Les prospections existantes restent rattachées à l'élève lors du changement de centre.

Les tests du Lot 4 se lancent avec `python manage.py test staff.tests.test_actions`. Aucune migration n'est requise pour ce lot.

## Tests

Après la génération de la migration locale 0001 et l'application des migrations :

    python manage.py test comptes.tests
    coverage run manage.py test
    coverage report

Les tests du Lot 1 couvrent les modèles, le consentement, les sessions, la journalisation des connexions et le workflow d'inscription. Les tests du Lot 2 couvrent les entreprises, les filtres, les formulaires et les vues.

## Vérifications manuelles du Lot 1

1. Lancez le serveur et ouvrez /, /comptes/inscription/ et /comptes/connexion/ sans session.
2. Inscrivez un élève avec un centre, une formation de ce centre et la case de consentement cochée. Vérifiez la redirection vers la connexion et l'affichage du compte et de son consentement dans l'administration.
3. Refaites une inscription sans accepter le consentement, puis avec une formation rattachée à un autre centre. Dans les deux cas, le formulaire doit être refusé et aucun compte ne doit être créé.
4. Connectez-vous comme eleve_attente_demo. La page d'accueil doit rediriger vers /comptes/en-attente/. La déconnexion doit rester accessible.
5. Connectez-vous comme admin_demo, validez le compte d'un élève depuis l'administration, puis vérifiez que cet élève peut accéder à l'accueil après reconnexion et que l'action est visible dans le journal.
6. Renseignez un motif sur un autre compte élève, appliquez l'action de refus et vérifiez que le motif apparaît sur sa page d'attente.
7. Connectez un compte élève dans une fenêtre, désactivez-le depuis une autre session d'administration, puis vérifiez que son ancienne session n'accède plus aux pages protégées.
