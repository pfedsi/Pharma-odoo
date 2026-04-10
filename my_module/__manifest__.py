
# -*- coding: utf-8 -*-
{
    'name': 'Q-Pharma OCR Ordonnance',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Fournit la clé OpenAI à l\'app mobile pour OCR des ordonnances',
    'description': """
Q-Pharma TN — OCR Ordonnance
==============================
Architecture :
  1. App mobile appelle GET /qpharma/ocr/apikey  → récupère la clé OpenAI
  2. App mobile appelle directement OpenAI GPT-4o Vision
  3. App mobile affiche les médicaments extraits

Endpoints exposés :
  GET  /qpharma/ocr/apikey   → retourne la clé OpenAI (token mobile requis)
  GET  /qpharma/ocr/ping     → health-check public
    """,
    'author': 'Q-Pharma TN',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/res_config_settings_views.xml',
        'views/favicon.xml',

    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}