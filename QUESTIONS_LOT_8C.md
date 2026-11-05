# Lot 8c — Type de contrat sur Prospection

- Le type de contrat est enregistré sur chaque prospection : Stage ou Alternance.
- En base, les anciennes et nouvelles lignes ont « alternance » par défaut.
- À la création, le formulaire élève et le formulaire staff exigent un choix explicite, sans choix précoché.
- Les tableaux élève, staff et administration permettent de filtrer par type de contrat et affichent la valeur.
- L’export CSV des prospections place `type_contrat` après `statut` et avant `date_creation`.
- Aucune migration n’est incluse dans ce commit ; elle sera générée localement avec `makemigrations entreprises`.
