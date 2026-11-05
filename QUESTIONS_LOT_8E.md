# Lot 8e — Hub superviseur et admin

- Le hub /hub/ est accessible aux superviseurs et aux admins ; les élèves reçoivent une réponse 403.
- Les cartes du hub sont adaptées au rôle.
- /prospections/ accepte les segments mine=1, eleves=1 et superviseurs=1.
- Les segments sont exclusifs, avec priorité mine > eleves > superviseurs.
- Un superviseur ne peut jamais consulter le segment des prospections des superviseurs.
- Les filtres statut, type de contrat, recherche, tri et pagination restent applicables au segment choisi.
- /dashboard/ et /staff/ restent inchangés.
- Aucune migration n'est nécessaire.
