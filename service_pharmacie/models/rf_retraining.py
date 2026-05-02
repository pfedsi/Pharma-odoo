#RZ: ici jai fais le factory de fichier .pkl  j'ai mis le model pour le réentrainement du modéle de random forest 
#RZ:j'ai mis les paremtre de reéntrainment chaque 2 mois et avec un minimum de 100 ticket 
from odoo import api, models, fields
from datetime import timedelta
import os
import shutil
import joblib
import pandas as pd
import logging

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

_logger = logging.getLogger(__name__)

BASE_RF_DIR = "/opt/odoo-custom-addons/rf"  
ACTIVE_MODEL_PATH = os.path.join(BASE_RF_DIR, "rf_global_service_duration.pkl")#RZ: j'ai mis un chemin pour le model actif
MODELS_DIR = os.path.join(BASE_RF_DIR, "models")
ARCHIVE_DIR = os.path.join(BASE_RF_DIR, "archive")#RZ: j'ai mis un dossier pour les nouveau model et un dossier pour les model archivé


class PharmacyRFRetraining(models.AbstractModel):
    _name = "pharmacy.rf.retraining"
    _description = "Réentraînement du modèle Random Forest"

    @api.model
    def retrain_model(self, days=None, min_records=None):

        params = self.env["ir.config_parameter"].sudo()

        enabled = params.get_param("service_pharmacie.rf_retraining_enabled", "True")
        #RZ: j'ai mis un parametre pour activer ou désactiver le réentrainement du model de random forest via les paramètres généraux d'odoo
        if enabled != "True":
            _logger.info("RF RETRAINING désactivé via paramètres")
            return {"status": "disabled"}

        if days is None:
            days = int(params.get_param("service_pharmacie.rf_retraining_days", 60))
            #RZ: j'ai mis un parametre pour définir la période de réentrainement du model de rf ici par défaut 60 jours
        if min_records is None:
            min_records = int(params.get_param("service_pharmacie.rf_retraining_min_records", 100))
        os.makedirs(MODELS_DIR, exist_ok=True)
        #RZ: j'ai mis une vérification pour créer les dossiers si ils n'existent pas déjà
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

        now = fields.Datetime.now()
        date_limit = now - timedelta(days=days)
    
        records = self.env["pharmacy.queue.history"].search([
            ("ticket_id", "!=", False),
            ("service_id", "!=", False),
            ("assistant_id", "!=", False),
            ("file_id", "!=", False),
            ("date_debut_traitement", "!=", False),
            ("date_fin_traitement", "!=", False),
            ("date_fin_traitement", ">=", date_limit),
        ])
    #RZ: j'ai mis une recherche pour récupérer les données de la table history qui sont nécessaire pour le réentrainement du model de random forest en filtrant sur la période définie et en vérifiant que les champs nécessaires ne sont pas vides
        rows = []

        for rec in records:
            duration = (
                rec.date_fin_traitement - rec.date_debut_traitement
            ).total_seconds() / 60.0
            #RZ: j'ai mis une vérification pour ne prendre en compte que les tickets dont la durée est entre 1 minute et 60 minutes pour éviter les outliers qui peuvent fausser le modèle de random forest
            if duration < 1 or duration > 60:
                continue

            dt = rec.date_debut_traitement

            rows.append({
                "assistant_id": rec.assistant_id.id or 0,
                "service_id": rec.service_id.id or 0,
                "file_id": rec.file_id.id or 0,
                "mode_rattachement": rec.mode_rattachement or "manuel",
                "poste_number": rec.poste_number or "P1",
                "heure_debut": dt.hour,
                "minute_debut": dt.minute,
                "jour_semaine": dt.weekday(),
                "mois": dt.month,
                "weekend": 1 if dt.weekday() >= 5 else 0,
                "dure_estimee_par_defaut": rec.service_id.dure_estimee_par_defaut or 15.0,
                "duration_real": duration,
            })

        if len(rows) < min_records:#verification 
            
            _logger.info(
                "RF RETRAINING annulé : historique insuffisant %s/%s",
                len(rows),
                min_records,
            )
            return {
                "status": "skipped",
                "reason": "not_enough_records",
                "records": len(rows),
            }

        df = pd.DataFrame(rows)
        #RZ: j'ai mis la préparation des données pour le réentrainement du model de random forest en créant un dataframe à partir des données récupérées et en préparant les features et la target pour l'entraînement du modèle de random forest
        X = df.drop(columns=["duration_real"]) #RZ :en enleve la colonne de la target pr RF
        #RZ: j'ai mis la transformation des variables catégorielles en variables numériques pour le modèle de random forest en utilisant la fonction get_dummies de pandas
        y = df["duration_real"]

        X = pd.get_dummies(  X,columns=["mode_rattachement", "poste_number"],drop_first=False, )

        X_train, X_test, y_train, y_test = train_test_split(   X,y,test_size=0.2,random_state=42,
        )#RZ: j'ai mis la séparation des données en un ensemble d'entraînement et un ensemble de test pour le réentrainement du model de random forest en utilisant la fonction train_test_split de scikit-learn

        new_model = RandomForestRegressor( n_estimators=200, random_state=42, min_samples_leaf=2,
        )#RZ : n_estimators : nombre d'arbres dans la forêt, min_samples_leaf : nombre minimum d'échantillons requis pour être à une feuille de l'arbre, random_state : pour la reproductibilité des résultats

        new_model.fit(X_train, y_train)#RZ : model rf commence à s'entrainer sur les données d'entrainement préparé

        new_pred = new_model.predict(X_test)
        new_mae = mean_absolute_error(y_test, new_pred) #RZ : MAE erreur moyenne 

        old_mae = None

        if os.path.exists(ACTIVE_MODEL_PATH):
            try:
                old_model = joblib.load(ACTIVE_MODEL_PATH)
                old_pred = old_model.predict(X_test)
                old_mae = mean_absolute_error(y_test, old_pred)
            except Exception as e:
                _logger.warning("Impossible de tester l'ancien modèle RF : %s", e)

        timestamp = now.strftime("%Y_%m_%d_%H%M")
        new_model_path = os.path.join(
            MODELS_DIR,
            f"rf_model_{timestamp}_mae_{round(new_mae, 2)}.pkl",
        )

        joblib.dump(new_model, new_model_path)

        is_better = old_mae is None or new_mae < old_mae

        if is_better:
            if os.path.exists(ACTIVE_MODEL_PATH):
                archive_path = os.path.join(
                    ARCHIVE_DIR,
                    f"old_rf_global_service_duration_{timestamp}.pkl",
                )
                shutil.copy2(ACTIVE_MODEL_PATH, archive_path)

            shutil.copy2(new_model_path, ACTIVE_MODEL_PATH)

            # important : vider le cache du modèle chargé ici on vide le cache pour que le model lis le model qui existe sur le disque 
            self.env["pharmacy.rf.predictor"].__class__._rf_model_cache = None

            status = "updated"
        else:
            status = "kept_old_model"

        _logger.info(
            "RF RETRAINING status=%s records=%s new_mae=%s old_mae=%s model=%s",
            status,
            len(df),
            round(new_mae, 3),
            round(old_mae, 3) if old_mae is not None else None,
            new_model_path,
        )

        return {
            "status": status,
            "records": len(df),
            "new_mae": round(new_mae, 3),
            "old_mae": round(old_mae, 3) if old_mae is not None else None,
            "new_model_path": new_model_path,
        }