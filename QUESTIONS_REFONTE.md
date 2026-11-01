# Refonte Entreprise / Prospection

## Décisions retenues

- `Entreprise` est le référentiel partagé : ses informations décrivent l'organisation et son nom est unique sans distinction de casse.
- `Prospection` relie un élève à une entreprise et porte le statut, les dates, les notes, la source et l'historique de sa démarche.
- Un élève ne peut avoir qu'une prospection pour une entreprise ; plusieurs élèves peuvent prospecter la même entreprise.
- Les vues élève ne chargent que les prospections de l'utilisateur connecté.
- La recherche authentifiée `/entreprises/search/` renvoie au plus 10 résultats, limités à `id`, `nom` et `ville` ; elle ne divulgue aucun statut ni note.
- Les superviseurs et administrateurs peuvent créer des prospections selon les règles de scope du Lot 4. Les journaux d'ajout et de changement de statut ciblent désormais une `Prospection`.
- La base de développement sera supprimée et recréée. Il n'y a aucune migration de données ; la migration de schéma sera générée localement par l'utilisateur avec `makemigrations`.

## Questions en attente

Aucune question en attente dans le périmètre validé.
