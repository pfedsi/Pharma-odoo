{
    'name': "service_pharmacie",
    'summary': "Gestion des services de pharmacie",
    'description': "Module de gestion des services de pharmacie",
    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/service_views.xml',
        'views/service_menu.xml',
    ],
    'installable': True,
    'application': True,
}