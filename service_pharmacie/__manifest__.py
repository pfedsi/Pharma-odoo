# -*- coding: utf-8 -*-
{
    "name": "Pharmacy Queue – Service",
    "version": "19.0.1.0.0",
    "summary": "Réservations et files d'attente pharmacie",
    "category": "Healthcare",
    "depends": ["base", "mail", "web", "point_of_sale", "product", "stock"],
    "data": [
        "security/ir.model.access.csv",

        "data/sequence_mobile_order.xml",
        "views/localization_views.xml",
        "views/ticket_display.xml",
        "views/ResConfigSettings.xml",
        "views/ticket_acces.xml",
        "views/display_templates.xml",
        "views/service_views.xml",
        "views/reservation_views.xml",
        "views/queue_views.xml",
        "views/ticket_views.xml",
        "views/rattachement_views.xml",
        "views/pharmacy_queue_history.xml",
        "views/prescription_views.xml",
        "views/product_template_views.xml",
        "views/inventaire_views.xml",
        "views/service_menu.xml",

        "views/mobile_order_views.xml",

        "data/medicament_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "service_pharmacie/static/src/js/map_picker.js",
            "service_pharmacie/static/src/scss/map_picker.scss",
        ],
        "web.assets_frontend": [
            "service_pharmacie/static/src/js/ticket_display.js",
            "service_pharmacie/static/src/css/pharmacy_display.css",
            "service_pharmacie/static/src/css/ticket_display.css",
        ],
        "point_of_sale._assets_pos": [
            "service_pharmacie/static/src/scss/rattachement.scss",
            "service_pharmacie/static/src/js/pos_rattachement_button.js",
            "service_pharmacie/static/src/js/prescription_pos_native.js",
            "service_pharmacie/static/src/xml/pos_rattachement_button.xml",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}