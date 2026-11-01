# Questions et décisions — Lot 3

Aucune question bloquante ne reste en attente pour le Lot 3.

- Le dashboard staff trie par `username`, `last_name`, `centre__nom` ou `is_valide`, avec `username` croissant par défaut.
- La création d'un scope est journalisée par `SCOPE_CREE`; sa désactivation par `ACCES_SCOPE_REFUSE`.
- Le filtrage du dashboard staff reste simple et local à sa vue. Il n'utilise pas le `FiltreMixin` du Lot 2.
