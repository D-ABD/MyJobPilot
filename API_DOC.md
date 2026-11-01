# API_DOC.md — MyJobPilot

Version 0.1 — périmètre du Lot 1. Les routes ci-dessous sont des vues HTML Django ; elles ne constituent pas encore une API JSON.

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

/comptes/apres-login/ redirige un administrateur ou un superviseur vers /admin/. Un élève non validé est envoyé vers /comptes/en-attente/. Un élève validé voit un message indiquant que son tableau de bord sera disponible au Lot 2.
