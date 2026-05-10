{
    'name': 'SaaS Manager',
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/saas_client_views.xml',
    ],
    'installable': True,
    'application': True,
}