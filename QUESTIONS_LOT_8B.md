# Questions et décisions — Lot 8b

- Import CSV : les colonnes requises sont `username,email,first_name,last_name,centre,formation`. Les erreurs sont rapportées ligne par ligne ; les lignes valides sont créées avec un mot de passe aléatoire de 12 caractères et restent non validées.
- Chaque compte importé reçoit un consentement RGPD version 1.0, sans IP, avec user-agent `import_csv`.
- Les icônes PWA sont des fichiers placeholders vides à remplacer en production.
- Le service worker est servi à la racine et ne met en cache aucun espace authentifié.
- Pour résoudre la règle contradictoire sur le changement de statut, une action d'administration notifie l'élève propriétaire ; un élève qui change son propre statut n'est pas notifié.
- L'ajout d'une prospection notifie les superviseurs actifs concernés, l'élève si l'auteur est le staff, et un administrateur actif si un élève n'a aucun superviseur actif.
- Aucun hook de notification n'est ajouté à l'upload de documents.
