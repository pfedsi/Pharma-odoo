# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    qpharma_openai_api_key = fields.Char(
        string="Clé API OpenAI (OCR)",
        help="Clé secrète OpenAI (sk-...) pour l'OCR des ordonnances via l'app mobile.",
        config_parameter='qpharma_ocr.openai_api_key',
    )

    qpharma_openai_model = fields.Char(
        string="Modèle OpenAI",
        help="Modèle à utiliser, ex: gpt-4o (défaut).",
        config_parameter='qpharma_ocr.openai_model',
        default='gpt-4o',
    )