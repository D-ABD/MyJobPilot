# Lot 8d — Prospections pour tous les rôles

- Le champ Prospection.eleve conserve son nom et peut référencer tout compte utilisateur.
- /prospections/ s'ajoute au dashboard élève et présente les lignes autorisées selon le rôle.
- Un élève crée pour lui-même ; un superviseur pour lui-même ou un élève de son scope ; un admin pour lui-même, un élève ou un superviseur.
- Les superviseurs ne voient pas les prospections d'autres superviseurs.
- Une création par un autre utilisateur est journalisée avec ACTION_STAFF_ELEVE et notifie le propriétaire via le service existant.
- Aucune migration n'est nécessaire.
