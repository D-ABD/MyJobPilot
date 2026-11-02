# Lot 5 — Documents

## Décisions appliquées

- Les documents sont stockés dans le champ binaire du modèle Document.
- Un fichier est limité à 5 Mo et le quota par élève est de 20 Mo.
- Les listings utilisent Document.objects.listing() et ne chargent pas le binaire.
- L'élève accède uniquement à ses documents.
- Le superviseur consulte et télécharge uniquement les documents d'un élève couvert par son scope actif ; il ne peut ni ajouter ni supprimer.
- L'administrateur peut consulter les documents de tous les élèves.
- Les envois, téléchargements et suppressions alimentent JournalAction.
- La migration du modèle sera générée localement par makemigrations documents.

## Questions en attente

Aucune question en attente dans le périmètre validé.
