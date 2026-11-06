# Questions Lot 9 — Documentation API et endpoint JSON

## Décisions retenues

- Aucun frontend React n'est inclus dans ce lot.
- Le seul nouvel endpoint est GET /api/prospections/, déclaré à la racine dans myjobpilot/urls.py.
- Le périmètre suit le rôle : prospections propres à l'élève ; prospections du superviseur et des élèves de son scope actif ; toutes les prospections pour l'admin.
- L'authentification utilise les sessions Django via DRF SessionAuthentication et IsAuthenticated ; aucun JWT ni token n'est ajouté.
- OpenAPI 3.0.3 décrit les trois endpoints JSON demandés : prospections, compteur de notifications et recherche d'entreprises.
- La documentation suit les routes réellement définies, notamment /documents/ajouter/ et /static/manifest.json.
- Aucun modèle ne change ; aucune migration n'est prévue.
