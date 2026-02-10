# prix/__manifest__.py (Code Complet et Corrigé)
{
    'name': "Vente de Mazout Dynamique",
    'summary': """
        Permet aux clients de saisir une quantité et d'afficher le prix dynamique 
        pour la vente de mazout en ligne (Odoo eCommerce).
    """,
    'description': """
        Ce module étend Odoo eCommerce pour :
        - Ajouter un contrôleur pour le calcul du prix.
        - Ajouter un champ de quantité dynamique sur la page produit.
        - Mettre à jour le prix via AJAX en fonction de la quantité saisie.
    """,
    'author': "Votre Nom",
    'website': "http://www.votre-site.com",

    # Catégories Odoo (facultatif mais recommandé)
    'category': 'Website/Website', 
    'version': '18.0.1.0.0',

    # Dépendances (modules nécessaires au fonctionnement)
    'depends': [
        'website_sale',
        'product',
        'website',
        'web_editor',
    ],

    # Fichiers de données (XML, CSV, etc.)
    'data': [
        'views/fuel_order_common.xml', 
        'views/fuel_order_custom_template.xml',
        'views/fuel_order_ultra_template.xml',
        'views/home_price.xml',
        'views/home_priceu.xml',
        'views/mazout_signup.xml',
        'views/disable_province.xml'
    ],
    
    # CRITIQUE : DÉCLARATION DES ASSETS AVEC DÉPENDANCES
    
    'assets': {
        'web.assets_frontend': [
            'prix/static/src/js/fuel_price.js',
            'prix/static/src/css/custom_order.css',
        ],
    },
    
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}