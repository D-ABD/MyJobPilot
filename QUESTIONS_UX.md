# Questions et décisions — Lot UX

- **Page Mon compte :** créée en lecture seule pour tous les rôles, avec les informations du compte et les liens correspondant au rôle. La modification renvoie provisoirement vers l'administration Django.
- **Contact du pied de page :** adiattalud@gmail.com.
- **Page 404 :** le gestionnaire est déclaré dans `myjobpilot/urls.py` et testé par appel direct de la vue.
- **Composants réutilisables :** partials pour le bouton retour, le fil d’Ariane et les états vides.
- **Navigation :** menu utilisateur adapté au rôle, avec les liens de compte et de navigation existants.
- **Affichage :** ajout de compteurs, d’états vides et d’une pagination avec première/dernière page et position courante.
- **Migrations :** aucune migration n’est nécessaire pour ce lot.
