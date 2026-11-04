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

Les élèves validés peuvent créer, modifier, consulter et supprimer leurs propres prospections depuis /dashboard/. Les entreprises sont partagées dans le référentiel ; chaque prospection conserve le statut et l'historique propres à l'élève. Le dashboard propose des filtres combinables, un tri par colonne et une pagination de 25 lignes. La recherche du Lot 2 ignore la casse ; la normalisation des accents est reportée au Lot 8a.

Les tests du Lot 2 se lancent avec python manage.py test entreprises.tests. Les fichiers de migration de modèles sont générés localement avec makemigrations entreprises ; aucune migration de ce lot n'est versionnée ici.

## Lot 3 — Scopes et dashboard superviseur

Les superviseurs voient uniquement les élèves rattachés aux centres de leurs scopes actifs. Leur dashboard permet de rechercher un élève, de filtrer par centre et par état de validation, de trier par identifiant, nom, centre ou état de validation, et de parcourir les résultats par pages de 25. La fiche élève affiche ses informations et ses entreprises en lecture seule.

Les scopes peuvent être créés et désactivés depuis l'administration Django. Leur création est journalisée par `SCOPE_CREE` et leur désactivation par `ACCES_SCOPE_REFUSE`. Une désactivation conserve l'enregistrement du scope.

Les tests du Lot 3 se lancent avec `python manage.py test staff.tests comptes.tests` après génération locale des migrations du modèle `ScopeSuperviseur`.

## Lot 4 — Actions staff sur les élèves

Depuis la fiche staff d'un élève, un administrateur peut changer son centre ou lui ajouter une prospection. Un superviseur peut effectuer ces deux actions uniquement sur un élève de son scope actif ; le changement de centre est limité à ses centres de scope. Les changements de centre et ajouts de prospection sont inscrits dans JournalAction. Les prospections existantes restent rattachées à l'élève lors du changement de centre.

Les tests du Lot 4 se lancent avec `python manage.py test staff.tests.test_actions`. Aucune migration n'est requise pour ce lot.

## Refonte — Entreprise et Prospection

Le modèle `Entreprise` constitue un référentiel partagé. Les informations générales d'une entreprise ne sont enregistrées qu'une fois, avec un nom unique sans distinction de casse. Le modèle `Prospection` relie un élève à une entreprise et porte les données personnelles de sa démarche : statut, dates, source, notes et historique. Un même élève ne peut créer qu'une prospection par entreprise ; plusieurs élèves peuvent prospecter la même entreprise.

Les vues élève filtrent strictement les prospections par compte connecté. L'autocomplete authentifié `/entreprises/search/?q=...` ne renvoie que l'identifiant, le nom et la ville de l'entreprise, dans une limite de 10 résultats. Il ne renvoie aucune information sur les démarches d'autres élèves.

La base de développement étant recréée pour cette refonte, aucune migration de données n'est prévue. Après sauvegarde puis suppression de `db.sqlite3`, générez et appliquez localement les migrations avec `python manage.py makemigrations` puis `python manage.py migrate`, avant `python manage.py creer_demo`.

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


## Lot 5 — Documents

Les élèves peuvent téléverser leurs documents (CV, lettre de motivation, diplôme ou autre) depuis leur espace dédié. Chaque fichier est limité à 5 Mo et le quota par élève est de 20 Mo. Les documents sont stockés dans un BinaryField et les listes utilisent un manager qui ne charge pas le contenu binaire.

Un élève ne voit que ses documents. Un superviseur peut les consulter et les télécharger pour un élève de son scope actif, sans pouvoir les ajouter ou les supprimer. L'administrateur peut consulter les documents de tous les élèves. Les envois, téléchargements et suppressions sont journalisés.


## Lot 6 — Commentaires et notifications in-app

Les élèves, les superviseurs de leur scope et les administrateurs peuvent commenter les prospections visibles selon leurs permissions. L'auteur ou un administrateur peut supprimer un commentaire. La création est journalisée.

Les notifications sont personnelles et consultables dans l'application. Un compteur non lu est actualisé toutes les 60 secondes. Les notifications créées au Lot 6 concernent les commentaires ; les hooks de validation de compte, changement de statut et ajout de document sont reportés au Lot 8b.


## Lot 7 — RGPD

Les élèves peuvent créer et suivre leurs demandes RGPD, et télécharger un export JSON de leurs données. L'export exclut le contenu binaire des documents. La politique de confidentialité version 1.0 est accessible sur `/confidentialite/` ; les coordonnées du responsable ou DPO doivent être renseignées avant mise en production.

Les commandes `purge_rgpd` et `purge_journal` prennent l'option `--dry-run`. La première purge les comptes désactivés après 1095 jours (référence `last_login`, ou `date_joined` s'il n'y a pas de connexion) et les comptes élèves non validés après 180 jours. La seconde supprime les entrées de journal de plus de 1095 jours. La purge du journal écrit son bilan via le logger `comptes` dans `logs/app.log`.

Exemple de planification cron (à adapter aux chemins et à l'heure retenue pour le serveur) :

    <minute> <heure> * * * /chemin/vers/venv/bin/python /chemin/vers/projet/manage.py purge_rgpd
    <minute> <heure> * * * /chemin/vers/venv/bin/python /chemin/vers/projet/manage.py purge_journal

Avant d'activer ces tâches, valider les durées, la politique et le calendrier de purge avec le responsable du traitement.


## Lot 8a — Dashboard administrateur et exports

Le dashboard administrateur affiche les principaux volumes du service et signale les demandes RGPD ouvertes depuis plus de 25 jours. Les pages d'élèves, superviseurs, scopes et demandes RGPD sont paginées à 25 lignes. La gestion des superviseurs permet de créer un compte avec son premier scope, puis d'ajouter ou de désactiver des scopes.

La page des exports produit quatre fichiers CSV pour les élèves, les prospections, l'historique des statuts et les demandes RGPD. Ils sont encodés en UTF-8 avec BOM pour une ouverture correcte dans Excel. Chaque téléchargement est inscrit dans le journal par `EXPORT_CSV`.


Les fiches administrateur du Lot 8a permettent de consulter les données liées à un élève, gérer les comptes élèves et superviseurs, et intervenir sur les statuts et commentaires des prospections. La désactivation invalide les sessions actives ; la suppression d'un superviseur exige une confirmation et supprime aussi ses scopes.
