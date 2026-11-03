# Lot 7 — RGPD

## Décisions appliquées

- Les demandes RGPD sont stockées dans l'application `rgpd` et appartiennent à un utilisateur.
- Le formulaire recueille un type de demande et une description facultative.
- Les élèves ne voient et n'exportent que leurs propres données et demandes.
- Les transitions de statut sont journalisées avec `DEMANDE_RGPD_MAJ`.
- Les comptes désactivés sont évalués avec `last_login` comme repère, ou `date_joined` si `last_login` est nul.
- Les comptes élèves non validés sont évalués selon `date_joined`.
- La purge du journal utilise une durée de rétention de 1095 jours et ne crée pas de `JournalAction`.
- Les migrations seront générées localement avec `makemigrations`.

## À compléter avant mise en production

- Remplacer les coordonnées de contact provisoires de la politique par celles du responsable du traitement ou du DPO.
- Vérifier et valider le contenu de la politique, notamment les bases légales, les destinataires et les durées de conservation des sauvegardes.
- Adapter les lignes cron aux chemins et à la fréquence retenus pour l'environnement de déploiement.
