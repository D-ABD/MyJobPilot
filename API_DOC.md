# API et routes MyJobPilot

Version 0.9 — application Django rendue côté serveur, avec une API JSON en lecture seule pour préparer une éventuelle intégration progressive. Aucun frontend React n'est inclus.

## Conventions

- Les pages HTML utilisent la session Django ; les formulaires POST sont protégés par CSRF.
- L'API /api/prospections/ utilise Django REST Framework, SessionAuthentication et IsAuthenticated. Aucun JWT ni jeton API n'est configuré.
- Les formulaires valides redirigent généralement en 302 ; un formulaire invalide est réaffiché en 200. Les accès interdits renvoient 403 et les ressources absentes 404.
- Les routes listées ci-dessous sont les URL réellement déclarées dans les URLconfs.

## Pages HTML — public, authentification et élève

| Méthode | URL | Rôle | Description | Paramètres | Réponses |
|---|---|---|---|---|---|
| GET | / | Public | Page d'accueil. | — | 200 HTML |
| GET, POST | /comptes/inscription/ | Public | Demande de création d'un compte élève avec consentement requis. | POST : username, first_name, last_name, email, centre, formation, password1, password2, consentement_rgpd | 200 HTML, 302 |
| GET, POST | /comptes/connexion/ | Public | Formulaire et ouverture de session. | POST : identifiant, mot de passe | 200 HTML, 302 |
| POST | /comptes/deconnexion/ | Connecté | Ferme la session. | CSRF | 302 |
| GET | /comptes/apres-login/ | Connecté | Redirige selon rôle et validation. | — | 302 |
| GET | /comptes/en-attente/ | Élève non validé | Affiche l'état de la demande de compte. | — | 200 HTML |
| GET | /mon-compte/ | Connecté | Profil en lecture seule. | — | 200 HTML |
| GET | /dashboard/ | Élève | Tableau de bord de ses prospections. | statut, type_contrat, date_debut, date_fin, q, tri, ordre, page | 200 HTML |
| GET | /entreprises/nouvelle/ | Élève | Formulaire historique de création d'une prospection. | POST : entreprise, statut, type_contrat, dates, notes, source | 200 HTML, 302, 403 |
| GET | /entreprises/<pk>/ | Élève propriétaire | Détail d'une prospection et de son historique/commentaires. | pk | 200 HTML, 403, 404 |
| GET, POST | /entreprises/<pk>/modifier/ | Élève propriétaire | Modifie une prospection. | POST : champs de prospection | 200 HTML, 302, 403, 404 |
| GET, POST | /entreprises/<pk>/supprimer/ | Élève propriétaire | Confirme puis supprime une prospection. | POST de confirmation | 200 HTML, 302, 403, 404 |
| GET, POST | /entreprises/<pk>/statut/ | Élève propriétaire | Modifie statut et dates associées, ajoute à l'historique. | POST : statut, date associée, commentaire | 200 HTML, 302, 403, 404 |
| GET, POST | /prospections/nouvelle/ | Élève, superviseur, admin | Crée une prospection pour un propriétaire permis selon le rôle. | POST : propriétaire, entreprise, type_contrat et autres champs | 200 HTML, 302, 403 |
| GET | /prospections/ | Connecté | Liste les prospections visibles selon le rôle. | mine, eleves, superviseurs, statut, type_contrat, date_debut, date_fin, q, tri, ordre, page | 200 HTML, superviseur avec superviseurs=1 : 403 |
| GET | /entreprises/search/ | Connecté | Autocomplete du référentiel ; au plus 10 résultats id/nom/ville, sans données de prospection. | q (facultatif) | 200 JSON, non connecté : 302 |
| POST | /commentaires/ajouter/<prospection_pk>/ | Propriétaire, superviseur du scope, admin | Ajoute un commentaire et journalise l'action. | POST : contenu | 302, 403, 404 |
| POST | /commentaires/<pk>/supprimer/ | Auteur ou admin | Supprime un commentaire. | CSRF | 302, 403, 404 |

Les paramètres mine, eleves et superviseurs sont exclusifs (priorité mine, puis eleves, puis superviseurs). Un superviseur voit ses propres prospections et celles des élèves de son scope actif ; un administrateur voit tout. Les autres filtres s'appliquent en complément. La pagination des listes est de 25 lignes.

## Documents et notifications

| Méthode | URL | Rôle | Description | Paramètres | Réponses |
|---|---|---|---|---|---|
| GET | /documents/ | Élève, admin | Liste des documents propres à l'élève ou tous les documents pour l'admin. | — | 200 HTML, 403 |
| GET, POST | /documents/ajouter/ | Élève | Téléverse un document (max. 5 Mo ; quota élève 20 Mo). | Multipart : fichier, nom, type | 200 HTML, 302 |
| GET | /documents/<pk>/telecharger/ | Propriétaire, superviseur du scope, admin | Télécharge un document autorisé. | pk | 200 fichier, 403, 404 |
| GET, POST | /documents/<pk>/supprimer/ | Propriétaire, admin | Confirme et supprime un document. | pk, POST de confirmation | 200 HTML, 302, 403, 404 |
| GET | /staff/eleves/<pk>/documents/ | Superviseur du scope, admin | Consultation en lecture seule des documents d'un élève. | pk élève | 200 HTML, 403, 404 |
| GET | /notifications/ | Connecté | Liste les notifications du destinataire. | — | 200 HTML |
| POST | /notifications/<pk>/marquer-lu/ | Destinataire | Marque sa notification comme lue. | CSRF | 302, 404 |
| POST | /notifications/marquer-tout-lu/ | Connecté | Marque ses notifications non lues comme lues. | CSRF | 302 |

## Superviseur, hub et actions staff

| Méthode | URL | Rôle | Description | Paramètres | Réponses |
|---|---|---|---|---|---|
| GET | /hub/ | Superviseur, admin | Hub avec raccourcis par rôle. | — | 200 HTML, élève : 403 |
| GET | /staff/ | Superviseur | Liste les élèves des centres de son scope actif. | q, centre, is_valide, tri, ordre, page | 200 HTML, 403 |
| GET | /staff/eleves/<pk>/ | Superviseur du scope, admin | Fiche staff d'un élève et prospections. | pk élève | 200 HTML, 403, 404 |
| GET, POST | /staff/eleves/<pk>/centre/ | Superviseur du scope, admin | Change le centre d'un élève. Le superviseur est limité à son scope actif. | POST : centre | 200 HTML, 302, 403, 404 |
| GET, POST | /staff/eleves/<pk>/entreprises/ajouter/ | Superviseur du scope, admin | Ajoute une prospection pour un élève autorisé. | POST : entreprise, type_contrat, autres champs | 200 HTML, 302, 403, 404 |

## Administration

Toutes les routes de cette section nécessitent le rôle admin ; les autres rôles authentifiés reçoivent 403.

| Méthode | URL | Description | Paramètres | Réponses |
|---|---|---|---|---|
| GET | /admin-dashboard/ | Statistiques et raccourcis admin. | — | 200 HTML |
| GET | /admin-dashboard/eleves/ | Liste filtrée et paginée des élèves. | q, centre, is_valide, tri, ordre, page | 200 HTML |
| GET | /admin-dashboard/eleves/<pk>/ | Fiche élève. | pk | 200 HTML, 404 |
| POST | /admin-dashboard/eleves/<pk>/valider/ | Valide un élève. | CSRF | 302, 404 |
| POST | /admin-dashboard/eleves/<pk>/refuser/ | Refuse un élève avec motif. | motif | 302, 404 |
| POST | /admin-dashboard/eleves/<pk>/desactiver/ | Désactive le compte et invalide ses sessions. | CSRF | 302, 404 |
| POST | /admin-dashboard/eleves/<pk>/reactiver/ | Réactive le compte. | CSRF | 302, 404 |
| GET, POST | /admin-dashboard/eleves/<pk>/centre/ | Change centre/formation de l'élève. | centre, formation | 200 HTML, 302, 404 |
| GET, POST | /admin-dashboard/eleves/<pk>/formation/ | Change la formation. | formation | 200 HTML, 302, 404 |
| GET | /admin-dashboard/superviseurs/ | Liste les superviseurs et leurs scopes. | page | 200 HTML |
| GET, POST | /admin-dashboard/superviseurs/creer/ | Crée un superviseur avec scope initial. | username, email, password, centre | 200 HTML, 302 |
| GET | /admin-dashboard/superviseurs/<pk>/ | Fiche superviseur. | pk | 200 HTML, 404 |
| GET, POST | /admin-dashboard/superviseurs/<pk>/modifier/ | Modifie le profil. | username, email, first_name, last_name | 200 HTML, 302, 404 |
| GET, POST | /admin-dashboard/superviseurs/<pk>/mot-de-passe/ | Change le mot de passe. | nouveau mot de passe et confirmation | 200 HTML, 302, 404 |
| POST | /admin-dashboard/superviseurs/<pk>/desactiver/ | Désactive et invalide les sessions. | CSRF | 302, 404 |
| POST | /admin-dashboard/superviseurs/<pk>/reactiver/ | Réactive le compte. | CSRF | 302, 404 |
| POST | /admin-dashboard/superviseurs/<pk>/supprimer/ | Supprime après confirmation. | CSRF, confirmation | 302, 404 |
| GET | /admin-dashboard/superviseurs/<pk>/scopes/ | Liste les scopes. | pk superviseur | 200 HTML, 404 |
| GET, POST | /admin-dashboard/superviseurs/<pk>/scopes/creer/ | Ajoute un scope. | centre | 200 HTML, 302, 404 |
| POST | /admin-dashboard/scopes/<pk>/desactiver/ | Désactive un scope. | CSRF | 302, 404 |
| GET | /admin-dashboard/demandes-rgpd/ | Liste filtrée des demandes et retards. | statut, type, tri, ordre, page | 200 HTML |
| GET, POST | /admin-dashboard/demandes-rgpd/<pk>/traiter/ | Traite ou refuse une demande RGPD. | statut, motif_refus | 200 HTML, 302, 404 |
| GET | /admin-dashboard/prospections/<pk>/ | Détail et historique d'une prospection. | pk | 200 HTML, 404 |
| POST | /admin-dashboard/prospections/<pk>/statut/ | Change le statut. | statut, dates, commentaire | 302, 404 |
| POST | /admin-dashboard/prospections/<pk>/commentaire/ | Ajoute un commentaire. | contenu | 302, 404 |
| GET | /admin-dashboard/exports/ | Page des téléchargements CSV. | — | 200 HTML |
| GET | /admin-dashboard/exports/eleves.csv | Export CSV des élèves. | — | 200 CSV |
| GET | /admin-dashboard/exports/prospections.csv | Export CSV des prospections. | — | 200 CSV |
| GET | /admin-dashboard/exports/historique.csv | Export CSV de l'historique. | — | 200 CSV |
| GET | /admin-dashboard/exports/demandes-rgpd.csv | Export CSV des demandes RGPD. | — | 200 CSV |
| GET, POST | /admin-dashboard/import-eleves/ | Import CSV des élèves avec rapport de lignes rejetées. | Multipart CSV : username,email,first_name,last_name,centre,formation | 200 HTML |

## RGPD et pages PWA

| Méthode | URL | Rôle | Description | Paramètres | Réponses |
|---|---|---|---|---|---|
| GET | /mon-compte/demandes-rgpd/ | Élève | Liste ses demandes RGPD. | — | 200 HTML |
| GET, POST | /mon-compte/demandes-rgpd/creer/ | Élève | Crée une demande. | type, description | 200 HTML, 302 |
| GET | /mon-compte/demandes-rgpd/<pk>/ | Propriétaire | Détail de sa demande. | pk | 200 HTML, 404 |
| GET | /mon-compte/export-rgpd/ | Élève | Télécharge un export JSON de ses données sans contenu binaire. | — | 200 JSON |
| GET | /confidentialite/ | Public | Politique de confidentialité. | — | 200 HTML |
| GET | /offline/ | Public | Page hors ligne. | — | 200 HTML |
| GET | /static/manifest.json | Public | Manifeste PWA. | — | 200 JSON |
| GET | /sw.js | Public | Service worker à la racine. | — | 200 JavaScript |

## Endpoints JSON existants

### GET /notifications/unread-count/

- Rôle : utilisateur connecté.
- Description : compte les notifications non lues du destinataire courant.
- Paramètres : aucun.
- Réponse : 200 JSON, objet {count: entier}. Sans session, la vue Django redirige vers la connexion (302).

### GET /entreprises/search/

- Rôle : utilisateur connecté.
- Description : recherche le nom dans le référentiel partagé ; jusqu'à 10 résultats id/nom/ville, sans statut ni données de prospection.
- Paramètres : q facultatif ; q vide retourne une liste vide.
- Réponse : 200 JSON, tableau. Sans session : 302 vers connexion.

## API JSON — Lot 9

### GET /api/prospections/

- Rôle : élève, superviseur ou admin connecté.
- Description : l'élève voit ses propres prospections ; le superviseur voit les siennes et celles des élèves de ses centres avec scope actif ; l'admin voit toutes les prospections.
- Paramètres : aucun.
- Authentification : session Django via SessionAuthentication, cookie sessionid ; aucun JWT ni token.
- Réponse : 200 application/json, tableau contenant id, entreprise (id, nom, ville), statut, statut_display, type_contrat, type_contrat_display, date_creation et date_modification. Les dates sont ISO 8601.
- Erreur : 403 si non authentifié ou rôle non autorisé.

Exemple :

    [
      {
        "id": 1,
        "entreprise": {"id": 1, "nom": "ACME Corp", "ville": "Paris"},
        "statut": "a_contacter",
        "statut_display": "À contacter",
        "type_contrat": "alternance",
        "type_contrat_display": "Alternance",
        "date_creation": "2026-01-15T10:30:00Z",
        "date_modification": "2026-01-15T10:30:00Z"
      }
    ]


## Référentiel des entreprises — Lot 10

| Méthode | URL | Rôle | Description | Paramètres | Réponses |
|---|---|---|---|---|---|
| GET | /entreprises-reference/ | Élève, superviseur, admin | Liste les entreprises visibles, avec filtres et pagination de 25 résultats. L'élève voit les entreprises de ses prospections ; le superviseur voit celles de son scope actif et ses propres prospections ; l'admin voit tout le référentiel. | q (nom, secteur, ville, sans distinction de casse ni d'accent), secteur, ville, tri (nom, ville, date_creation), ordre (asc/desc), page | 200 HTML, 403 |
| GET | /entreprises-reference/<pk>/ | Élève, superviseur, admin | Affiche les informations de l'entreprise et uniquement les prospections visibles pour le rôle courant. | pk | 200 HTML, 403, 404 |

Les paramètres de filtre sont conservés lors du tri et de la pagination. Le lien « Réinitialiser les filtres » revient à /entreprises-reference/ sans paramètre.

### Export du référentiel des entreprises — Lot 11

| Méthode | URL | Rôle | Description | Paramètres | Réponses |
|---|---|---|---|---|---|
| GET | /entreprises-reference/export.csv | Élève, superviseur, admin | Télécharge les entreprises visibles par le rôle courant ; l'export réutilise l'isolation et les filtres de la liste. Une exportation non vide est inscrite dans JournalAction avec son nombre de lignes et ses filtres. | q, secteur, ville, tri, ordre | 200 CSV UTF-8 avec BOM |
| GET | /api/entreprises/ | Élève, superviseur, admin | Retourne en JSON les entreprises visibles et leur nombre de prospections visibles. | q, secteur, ville | 200 JSON, 403 si session absente ou rôle non autorisé |

Le CSV contient nom, secteur, ville, code postal, site web, contact, date de création et nombre de prospections. L'API utilise la session Django et applique les mêmes règles d'isolation que `/entreprises-reference/`.
