# Lot 8a — Dashboard admin + exports CSV

## Décisions appliquées

- Dashboard et gestion administrative regroupés dans l'application dédiée `admin_dashboard`.
- Les templates du lot sont placés dans `templates/admin_dashboard/`.
- La désactivation d'un scope journalise `SCOPE_CREE` avec le détail `{"action": "desactivation"}`.
- La page d'ajout de scope est accessible en GET et reçoit le formulaire en POST sur la route dédiée.
- Les exports sont des CSV UTF-8 avec BOM, horodatés au jour local et journalisés par `EXPORT_CSV`.
- Aucun modèle ni migration n'est ajouté au Lot 8a.


## Actions de gestion ajoutées avant validation finale

- La fiche élève admin donne accès aux données liées et aux actions de validation, refus, désactivation, réactivation et rattachement centre/formation.
- La fiche superviseur admin permet la modification du profil, le changement du mot de passe, la désactivation, la réactivation et la suppression confirmée avec ses scopes.
- La fiche prospection admin permet de changer le statut et d'ajouter un commentaire.
- Les routes de ces actions restent réservées au rôle admin.
