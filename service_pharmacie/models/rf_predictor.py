from odoo import api, models, fields
import os
import joblib
import pandas as pd

MODEL_PATH = "/opt/odoo-custom-addons/rf/rf_global_service_duration.pkl"


class PharmacyRFPredictor(models.AbstractModel):
    _name = "pharmacy.rf.predictor"
    _description = "RF Predictor for Pharmacy Service Duration"

    _rf_model_cache = None

    @api.model
    def _load_model(self):
        if self.__class__._rf_model_cache is not None:
            return self.__class__._rf_model_cache

        if not os.path.exists(MODEL_PATH):
            return None

        try:
            self.__class__._rf_model_cache = joblib.load(MODEL_PATH)
            return self.__class__._rf_model_cache
        except Exception:
            return None

    @api.model
    def predict_duration(
        self,
        service_id,
        assistant_id=None,
        file_id=None,
        mode_rattachement="manuel",
        poste_number="P1",
        hour=None,
        minute=None,
        weekday=None,
        month=None,
        weekend=None,
        duree_defaut=15.0,
    ):
        model = self._load_model()
        if not model:
            return None

        now = fields.Datetime.now()
        hour = now.hour if hour is None else hour
        minute = now.minute if minute is None else minute
        weekday = now.weekday() if weekday is None else weekday
        month = now.month if month is None else month
        weekend = (1 if weekday >= 5 else 0) if weekend is None else weekend

        sample = pd.DataFrame([{
            "assistant_id": assistant_id or 0,
            "service_id": service_id or 0,
            "file_id": file_id or 0,
            "mode_rattachement": mode_rattachement or "manuel",
            "poste_number": poste_number or "P1",
            "heure_debut": hour,
            "minute_debut": minute,
            "jour_semaine": weekday,
            "mois": month,
            "weekend": weekend,
            "dure_estimee_par_defaut": duree_defaut or 15.0,
        }])

        try:
            return float(model.predict(sample)[0])
        except Exception:
            return None