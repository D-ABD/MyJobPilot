# Questions et décisions — Lot 4

## Décisions confirmées

- Le modèle `Centre` n'a pas de champ `actif` ; tous les centres existants sont considérés comme actifs. Le formulaire utilise `Centre.objects.all()` pour l'administrateur et les centres du scope actif pour le superviseur.
- L'administrateur peut consulter les fiches staff de tous les élèves et effectuer les deux actions du lot sur tout élève.
- Le superviseur peut effectuer les deux actions uniquement pour un élève de son scope actif. Il ne peut changer le centre que vers un centre de son scope actif.
- Un changement de centre conserve les prospections liées à l'élève.
- L'ajout d'une prospection utilise `EntrepriseForm`, crée l'entreprise au statut `A_CONTACTER`, crée l'historique initial et journalise l'action.
- Les actions sont journalisées avec `CHANGEMENT_CENTRE` et `ACTION_STAFF_ELEVE`, selon les détails spécifiés.
- Aucune migration n'est créée pour le Lot 4.

## Questions en attente

Aucune question en attente pour le périmètre validé du Lot 4.
