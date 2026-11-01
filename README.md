# MyJobPilot — Lot 1

Socle Django de l'application de prospection d'alternance : configuration, comptes, inscription, validation administrative et interface Bootstrap.

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

Avant la première migration, 0001_initial.py doit être générée localement. Comme la migration 0002_donnees_initiales.py référence 0001_initial.py, mettez temporairement 0002 de côté, générez 0001, puis restaurez 0002 :

    migration="comptes/migrations/0002_donnees_initiales.py"
    backup="comptes/migrations/0002_donnees_initiales.py.bak"
    mv "$migration" "$backup"
    python manage.py makemigrations comptes
    mv "$backup" "$migration"
    python manage.py check
    python manage.py migrate

    python manage.py creer_demo
    python manage.py runserver

Si makemigrations échoue, restaurez le fichier avec la commande mv indiquée avant de reprendre. Ne laissez pas le fichier .bak dans le dossier des migrations. La migration locale 0001_initial.py contient les modèles du socle, notamment le modèle utilisateur personnalisé et le consentement RGPD. La migration versionnée 0002_donnees_initiales.py ajoute les centres et formations de démonstration.

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
- entreprises/ : app préparée pour le Lot 2.
- documents/ : app préparée pour le Lot 5.
- rgpd/ : app préparée pour le Lot 7.
- core/ : app commune, sans logique métier à ce lot.
- templates/ et static/css/custom.css : interface française Bootstrap.

## Tests

Après la génération de la migration locale 0001 et l'application des migrations :

    python manage.py test comptes.tests
    coverage run manage.py test
    coverage report

Les tests du Lot 1 couvrent les modèles, le consentement, les sessions, la journalisation des connexions et le workflow d'inscription. Les seuils portant sur les modules des lots 2 à 7 seront vérifiables quand ces modules seront créés.

## Vérifications manuelles du Lot 1

1. Lancez le serveur et ouvrez /, /comptes/inscription/ et /comptes/connexion/ sans session.
2. Inscrivez un élève avec un centre, une formation de ce centre et la case de consentement cochée. Vérifiez la redirection vers la connexion et l'affichage du compte et de son consentement dans l'administration.
3. Refaites une inscription sans accepter le consentement, puis avec une formation rattachée à un autre centre. Dans les deux cas, le formulaire doit être refusé et aucun compte ne doit être créé.
4. Connectez-vous comme eleve_attente_demo. La page d'accueil doit rediriger vers /comptes/en-attente/. La déconnexion doit rester accessible.
5. Connectez-vous comme admin_demo, validez le compte d'un élève depuis l'administration, puis vérifiez que cet élève peut accéder à l'accueil après reconnexion et que l'action est visible dans le journal.
6. Renseignez un motif sur un autre compte élève, appliquez l'action de refus et vérifiez que le motif apparaît sur sa page d'attente.
7. Connectez un compte élève dans une fenêtre, désactivez-le depuis une autre session d'administration, puis vérifiez que son ancienne session n'accède plus aux pages protégées.
