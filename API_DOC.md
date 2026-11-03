# API_DOC.md — MyJobPilot

Version 0.5 — périmètres des Lots 1 à 4 et séparation du référentiel Entreprise des Prospections. Les routes ci-dessous sont des vues HTML Django, à l'exception de la recherche JSON ; elles ne constituent pas encore une API JSON complète.

## Authentification et inscription

| Méthode | Chemin | Accès | Comportement |
| --- | --- | --- | --- |
| GET | / | Public | Affiche la page d'accueil. |
| GET, POST | /comptes/inscription/ | Public | Affiche et traite la demande d'inscription d'un élève. |
| GET, POST | /comptes/connexion/ | Public | Affiche le formulaire et authentifie l'utilisateur. |
| POST | /comptes/deconnexion/ | Authentifié | Termine la session et redirige vers la connexion. |
| GET | /comptes/apres-login/ | Authentifié | Redirige selon le rôle et l'état de validation. |
| GET | /comptes/en-attente/ | Authentifié | Affiche l'état de validation de l'élève. |
| GET, POST | /admin/ | Staff autorisé | Administre les référentiels et traite les comptes. |

## POST /comptes/inscription/

Champs requis : username, first_name, last_name, email, centre, formation, password1, password2, consentement_rgpd.

consentement_rgpd est un booléen requis qui indique l'acceptation de la politique de confidentialité. Si le champ est absent ou vaut False, la soumission est refusée et le formulaire est affiché avec une erreur (HTTP 200). Si la formation n'appartient pas au centre choisi, le formulaire est également refusé.

En cas de succès, le compte est créé avec le rôle eleve et is_valide=False, le consentement version 1.0 est enregistré avec l'adresse IP et le user-agent disponibles, puis une action inscription_soumise est journalisée. Le navigateur est redirigé vers /comptes/connexion/.

## Validation dans l'administration

Un administrateur habilité peut sélectionner des comptes en attente depuis /admin/ et appliquer les actions suivantes :

- Valider : active le champ is_valide, renseigne la date et l'administrateur validateur, puis journalise compte_valide.
- Refuser : maintient is_valide=False et journalise compte_refuse. Le motif peut être renseigné dans la fiche utilisateur.
- Désactiver : définit is_active=False, invalide les sessions encore actives et journalise compte_desactive.

## Redirection après connexion

/comptes/apres-login/ redirige un administrateur vers /admin/, un superviseur vers /staff/, un élève non validé vers /comptes/en-attente/ et un élève validé vers /dashboard/.

## Lot 2 — Prospection élève

Toutes ces routes exigent une connexion. Elles sont réservées à l'élève connecté et ne retournent que ses propres entreprises. Les accès d'un superviseur ou d'un administrateur à ces vues renvoient HTTP 403.

| Méthode | Chemin | Comportement |
| --- | --- | --- |
| GET | /dashboard/ | Tableau de bord, filtres combinables, tri et pagination de 25 lignes. |
| GET | /entreprises/search/?q=... | Recherche authentifiée dans le référentiel. Retourne au plus 10 objets JSON contenant uniquement `id`, `nom` et `ville`. |
| GET, POST | /entreprises/nouvelle/ | Affiche et crée une Prospection liée à une entreprise existante ou à une nouvelle entrée du référentiel. |
| GET | /entreprises/<id>/ | Détail de la prospection de l'élève connecté et son historique. |
| GET, POST | /entreprises/<id>/modifier/ | Affiche et met à jour les données de prospection de l'élève. |
| GET, POST | /entreprises/<id>/supprimer/ | Confirme puis supprime la prospection et son historique ; l'entreprise partagée est conservée. |
| GET, POST | /entreprises/<id>/statut/ | Affiche et enregistre un changement de statut daté sur la prospection. |

Les filtres du dashboard sont transmis par paramètres GET : statut, date_debut, date_fin, q, tri, ordre et page. Ils portent uniquement sur les prospections de l'élève connecté ; la recherche interroge les informations de l'entreprise liée. La recherche est insensible à la casse. Les dates filtrent la date de modification de la prospection.

Le référentiel Entreprise est partagé et son nom est unique sans distinction de casse. Une Prospection relie un élève à une entreprise et porte son statut, ses dates, sa source et ses notes. Chaque élève ne peut avoir qu'une prospection par entreprise. L'endpoint de recherche ne renvoie aucune donnée de prospection.

## Lot 3 — Tableau de bord superviseur

Ces routes exigent une connexion et sont réservées aux superviseurs. Le dashboard ne liste que les élèves rattachés aux centres ayant un scope actif pour le superviseur. Un accès à la fiche d'un élève hors scope renvoie HTTP 403.

| Méthode | Chemin | Comportement |
| --- | --- | --- |
| GET | /staff/ | Dashboard des élèves des centres du scope, avec recherche, filtres, tri par colonne et pagination de 25 lignes. |
| GET | /staff/eleves/<id>/ | Fiche en lecture seule d'un élève du scope, avec la liste de ses entreprises. |

Les paramètres du dashboard sont `q`, `centre`, `is_valide`, `tri`, `ordre` et `page`. Le tri accepte `username`, `last_name`, `centre__nom` et `is_valide`; par défaut, les élèves sont triés par identifiant croissant. Les filtres de centre ne peuvent sélectionner que les centres couverts par un scope actif.

Les scopes sont gérés dans l'administration Django. Leur création est journalisée avec `SCOPE_CREE`; leur désactivation conserve l'enregistrement et journalise `ACCES_SCOPE_REFUSE`.

Actions ajoutées au journal au Lot 3 : `scope_cree` (création d'un scope superviseur) et `acces_scope_refuse` (désactivation d'un scope).

## Lot 4 — Actions staff sur les élèves

Les actions ci-dessous nécessitent une connexion. Un administrateur peut agir sur tout élève. Un superviseur peut agir uniquement sur un élève de son scope actif.

| Méthode | Chemin | Accès | Comportement |
| --- | --- | --- | --- |
| GET | /staff/eleves/<id>/ | Admin, superviseur du scope | Affiche la fiche élève et ses prospections ; cette fiche présente les actions autorisées. |
| GET, POST | /staff/eleves/<id>/centre/ | Admin ou superviseur du scope | Affiche et enregistre le changement de centre. Un superviseur ne peut choisir qu'un centre de son scope actif ; sinon l'accès est refusé (HTTP 403). L'action est journalisée par `CHANGEMENT_CENTRE`. |
| POST | /staff/eleves/<id>/entreprises/ajouter/ | Admin ou superviseur du scope | Crée une prospection pour l'élève, liée à une entreprise existante ou nouvellement créée, avec son historique initial. L'action est journalisée par `ACTION_STAFF_ELEVE` et cible la Prospection. |

Le changement de centre conserve les prospections existantes, qui restent liées à l'élève. Les centres proposés sont tous les centres pour l'administrateur et uniquement les centres du scope actif pour le superviseur. Les élèves n'ont pas accès à ces actions.


## Lot 5 — Documents

Les routes ci-dessous nécessitent une authentification. Les fichiers sont stockés dans Document.contenu ; les listings n'exposent pas le binaire.

| Méthode | Chemin | Accès | Comportement |
| --- | --- | --- | --- |
| GET | /documents/ | Élève, admin | Liste les documents propres à l'élève ; l'admin voit tous les documents. L'élève voit son quota utilisé sur 20 Mo. |
| GET, POST | /documents/ajouter/ | Élève | Téléverse un document, limité à 5 Mo, sous réserve du quota de 20 Mo. L'action est journalisée par DOCUMENT_UPLOAD. |
| GET | /documents/<id>/telecharger/ | Propriétaire, admin, superviseur du scope | Télécharge le document et journalise DOCUMENT_DOWNLOAD. |
| GET, POST | /documents/<id>/supprimer/ | Propriétaire, admin | Confirme puis supprime le document ; l'action est journalisée par DOCUMENT_SUPPRIME. |
| GET | /staff/eleves/<id>/documents/ | Admin, superviseur du scope actif | Consulte les documents de l'élève en lecture seule. L'accès hors scope est refusé (HTTP 403). |

Les superviseurs ne peuvent pas téléverser ou supprimer les documents. Les vues élève filtrent strictement sur l'utilisateur connecté.


## Lot 6 — Commentaires et notifications

| Méthode | Chemin | Accès | Comportement |
| --- | --- | --- | --- |
| POST | /commentaires/ajouter/<prospection_pk>/ | Élève propriétaire, superviseur du scope actif, admin | Crée un commentaire sur une prospection et journalise COMMENTAIRE_CREE. |
| POST | /commentaires/<pk>/supprimer/ | Auteur du commentaire, admin | Supprime le commentaire. |
| GET | /notifications/ | Utilisateur connecté | Liste les notifications du destinataire, non lues en premier. |
| GET | /notifications/unread-count/ | Utilisateur connecté | Retourne le nombre de notifications non lues sous la forme JSON {count: N}. |
| POST | /notifications/<pk>/marquer-lu/ | Destinataire | Marque sa notification comme lue. |
| POST | /notifications/marquer-tout-lu/ | Utilisateur connecté | Marque toutes ses notifications comme lues. |

Les notifications de commentaires sont envoyées aux superviseurs actifs du centre de l'élève ; en l'absence de superviseur actif, au premier admin actif. Un commentaire de superviseur ou d'admin notifie l'élève propriétaire s'il est actif. Les hooks des Lots 1 à 5 ne sont pas activés dans ce lot.


## Lot 7 — Droits RGPD

| Méthode | Chemin | Accès | Comportement |
| --- | --- | --- | --- |
| GET | /mon-compte/demandes-rgpd/ | Élève | Liste ses demandes. |
| GET, POST | /mon-compte/demandes-rgpd/creer/ | Élève | Affiche et crée une demande avec type et description facultative. |
| GET | /mon-compte/demandes-rgpd/<id>/ | Propriétaire | Consulte le détail de sa demande. |
| GET | /admin-dashboard/demandes-rgpd/ | Admin | Liste les demandes. |
| GET, POST | /admin-dashboard/demandes-rgpd/<id>/traiter/ | Admin | Met à jour le statut, le motif, la date de traitement et le responsable. |
| GET | /mon-compte/export-rgpd/ | Élève | Télécharge un JSON de ses données ; les fichiers binaires des documents sont exclus. |
| GET | /confidentialite/ | Public | Affiche la politique de confidentialité version 1.0. |

Les transitions de statut des demandes sont journalisées avec `DEMANDE_RGPD_MAJ`; les exports avec `EXPORT_RGPD`. `purge_rgpd --dry-run` liste les comptes concernés sans suppression. `purge_journal --dry-run` compte les entrées anciennes sans suppression.
