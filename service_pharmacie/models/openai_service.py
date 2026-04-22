import json
import requests
from PIL import Image
import base64
import io

from odoo import models, api, _
from odoo.exceptions import UserError


class PharmacyOpenAIService(models.AbstractModel):
    _name = "pharmacy.openai.service"
    _description = "OpenAI OCR Service"

    @api.model
    def _get_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = icp.get_param("qpharma_ocr.openai_api_key")
        model = icp.get_param("qpharma_ocr.openai_model") or "gpt-4o"

        return {
            "enabled": bool(api_key),
            "api_key": api_key,
            "model": model,
        }

    def _prepare_image_data(self, attachment):
        if not attachment or not attachment.datas:
            raise UserError(_("Aucun fichier ordonnance trouvé."))

        try:
            raw = base64.b64decode(attachment.datas)
            image = Image.open(io.BytesIO(raw))
            image.load()
        except Exception:
            raise UserError(_("Le fichier n'est pas une image valide (JPG, PNG, WEBP)."))

        out = io.BytesIO()

        # Gérer les images avec transparence ou palette
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
            image.save(out, format="PNG")
            mime_type = "image/png"
        else:
            image = image.convert("RGB")
            image.save(out, format="JPEG", quality=95)
            mime_type = "image/jpeg"

        clean_base64 = base64.b64encode(out.getvalue()).decode("utf-8")
        return mime_type, clean_base64
    @api.model
    def extract_prescription(self, attachment):
        cfg = self._get_config()

        if not cfg["api_key"]:
            raise UserError(_("Clé OpenAI manquante dans Paramètres IA."))

        mime_type, image_base64 = self._prepare_image_data(attachment)

        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }

        prompt = prompt = """
Tu es un assistant d'analyse d'ordonnances pharmaceutiques.

Ta mission se fait en 2 étapes :

ÉTAPE 1 — Vérifier s'il s'agit réellement d'une ordonnance
Analyse l'image et détermine si le document correspond à une ordonnance médicale/pharmaceutique.
Considère comme ordonnance un document contenant au moins plusieurs indices cohérents, par exemple :
- nom d'un médecin ou cachet médical
- nom du patient
- date
- médicaments prescrits
- posologie, dosage, durée, quantité
- structure typique d'une prescription

Si le document n'est pas clairement une ordonnance, retourne :
- is_prescription = false
- un motif court dans validation_reason
- medications = []

ÉTAPE 2 — Si c'est bien une ordonnance, extraire les médicaments
Extrais uniquement les médicaments réellement visibles sur l'image.
N'invente aucun médicament.
Si une information est absente, incomplète ou illisible, retourne une chaîne vide.

RÈGLES IMPORTANTES :
- Retourne uniquement un JSON valide
- Aucun texte hors JSON
- Ne fais aucune explication
- Ne complète pas par supposition
- Ne mélange pas plusieurs médicaments sur une seule ligne
- Chaque médicament doit être un objet séparé
- Le champ confidence doit être une valeur numérique entre 0 et 1
- Si l'image est floue, incomplète, non lisible, ou si ce n'est pas une ordonnance, indique-le clairement dans validation_reason

Le JSON doit respecter strictement cette logique :
- is_prescription : true ou false
- validation_reason : explication courte
- patient_name : texte
- doctor_name : texte
- prescription_date : texte
- medications : liste des médicaments extraits
"""

        schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "is_prescription": {"type": "boolean"},
            "validation_reason": {"type": "string"},
            "patient_name": {"type": "string"},
            "doctor_name": {"type": "string"},
            "prescription_date": {"type": "string"},
            "medications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "raw_label": {"type": "string"},
                        "drug_name": {"type": "string"},
                        "dosage": {"type": "string"},
                        "form": {"type": "string"},
                        "quantity": {"type": "string"},
                        "duration": {"type": "string"},
                        "confidence": {"type": "number"}
                    },
                    "required": [
                        "raw_label",
                        "drug_name",
                        "dosage",
                        "form",
                        "quantity",
                        "duration",
                        "confidence"
                    ]
                }
            }
        },
        "required": [
            "is_prescription",
            "validation_reason",
            "patient_name",
            "doctor_name",
            "prescription_date",
            "medications"
        ]
    }

        payload = {
            "model": cfg["model"],
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_base64}",
                        "detail": "high"
                    }
                ]
            }],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "prescription_extraction",
                    "schema": schema
                }
            }
        }

        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=payload,
            timeout=90,
        )

        if response.status_code >= 400:
            raise UserError(_("Erreur OpenAI : %s") % response.text)

        data = response.json()

        output_text = ""
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_text += content.get("text", "")

        if not output_text:
            raise UserError(_("Réponse vide d'OpenAI."))

        try:
            result = json.loads(output_text)

            if not result.get("is_prescription"):
                raise UserError(
                    _("Veuillez fournir une ordonnance valide.\n\nRaison : %s") 
                    % result.get("validation_reason", "Document non reconnu")
                )

            return result
        except Exception as e:
            raise UserError(_("JSON invalide retourné par OpenAI : %s") % str(e))