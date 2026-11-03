# Lot 6 — Commentaires et notifications in-app

## Décisions appliquées

- Commentaire est rattaché à Prospection dans l'application entreprises.
- Notification est rattachée à Utilisateur dans l'application comptes.
- Un élève peut commenter ses prospections ; un superviseur peut commenter celles de son scope actif ; un admin peut commenter toute prospection.
- Un commentaire d'élève notifie tous les superviseurs actifs du centre ; s'il n'y en a aucun, il notifie le premier admin actif.
- Un commentaire d'un superviseur ou d'un admin notifie l'élève propriétaire, uniquement si son compte est actif.
- La suppression d'un commentaire est réservée à son auteur ou à un admin.
- Seule la création d'un commentaire déclenche une notification au Lot 6. Les hooks des Lots 1 à 5 restent reportés au Lot 8b.
- Le compteur est actualisé par un appel JavaScript vanilla toutes les 60 secondes.

## Questions en attente

Aucune question en attente dans le périmètre validé.
