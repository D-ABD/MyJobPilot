# Lot 8a — Dashboard admin + exports CSV

## Décisions appliquées

- Dashboard et gestion administrative regroupés dans l'application dédiée `admin_dashboard`.
- Les templates du lot sont placés dans `templates/admin_dashboard/`.
- La désactivation d'un scope journalise `SCOPE_CREE` avec le détail `{"action": "desactivation"}`.
- La page d'ajout de scope est accessible en GET et reçoit le formulaire en POST sur la route dédiée.
- Les exports sont des CSV UTF-8 avec BOM, horodatés au jour local et journalisés par `EXPORT_CSV`.
- Aucun modèle ni migration n'est ajouté au Lot 8a.
