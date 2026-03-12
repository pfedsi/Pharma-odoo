{
    'name': "API Auth",
    'summary': "Authentication API for mobile app",
    'description': """
REST API for login, register and password reset
    """,
    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Tools',
    'version': '1.0',
    'depends': ['base', 'mail', 'auth_signup'],
    'data': [
        'views/views.xml',
        'views/templates.xml',
        'views/swagger_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}