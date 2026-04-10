import math
import joblib
import pandas as pd
from sqlalchemy import create_engine, text

# ============================================================
# CONFIG
# ============================================================

DB_USER = "odoo"
DB_PASSWORD = "12345678"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "pharmag"

MODEL_PATH = "/opt/odoo-custom-addons/rf/rf_global_service_duration.pkl"

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ============================================================
# HELPERS
# ============================================================

def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def get_recency_weight(age_days):
    if age_days <= 7:
        return 3.0
    elif age_days <= 14:
        return 2.0
    elif age_days <= 30:
        return 1.5
    return 1.0


def weighted_average(values):
    if not values:
        return 0.0
    total_weight = sum(v["weight"] for v in values)
    if not total_weight:
        return 0.0
    return sum(v["duration"] * v["weight"] for v in values) / total_weight


def compute_time_factor(hour, weekday, month):
    factor = 1.0

    # weekend
    if weekday >= 5:
        factor *= 1.05

    # heure de pointe approximative
    if 8 <= hour <= 10:
        factor *= 1.10
    elif 18 <= hour <= 21:
        factor *= 1.08
    elif 0 <= hour <= 6:
        factor *= 1.07

    if month in [12, 1]:
        factor *= 1.03

    return factor


def compute_assistant_count_factor(nb_assistants):
    if nb_assistants is None or nb_assistants <= 1:
        return 1.00
    elif nb_assistants == 2:
        return 0.97
    else:
        return 0.94


# ============================================================
# DATA ACCESS
# ============================================================

def get_service_info(service_id):
    query = text("""
        SELECT id, nom, dure_estimee_par_defaut, queue_id
        FROM pharmacy_service
        WHERE id = :service_id
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"service_id": service_id}).mappings().first()
    return row


def get_service_history(service_id, days=30):
    query = text("""
        SELECT
            EXTRACT(EPOCH FROM (h.date_fin_traitement - h.date_debut_traitement)) / 60.0 AS duration_min,
            EXTRACT(DAY FROM (NOW() - h.date_fin_traitement)) AS age_days
        FROM pharmacy_queue_history h
        WHERE h.service_id = :service_id
          AND h.ticket_id IS NOT NULL
          AND h.date_debut_traitement IS NOT NULL
          AND h.date_fin_traitement IS NOT NULL
          AND h.date_fin_traitement >= NOW() - (:days || ' days')::interval
          AND EXTRACT(EPOCH FROM (h.date_fin_traitement - h.date_debut_traitement)) / 60.0 BETWEEN 1 AND 180
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"service_id": service_id, "days": days}).mappings().all()
    return rows


def get_assistant_service_history(assistant_id, service_id, days=30):
    query = text("""
        SELECT
            EXTRACT(EPOCH FROM (h.date_fin_traitement - h.date_debut_traitement)) / 60.0 AS duration_min,
            EXTRACT(DAY FROM (NOW() - h.date_fin_traitement)) AS age_days
        FROM pharmacy_queue_history h
        WHERE h.assistant_id = :assistant_id
          AND h.service_id = :service_id
          AND h.ticket_id IS NOT NULL
          AND h.date_debut_traitement IS NOT NULL
          AND h.date_fin_traitement IS NOT NULL
          AND h.date_fin_traitement >= NOW() - (:days || ' days')::interval
          AND EXTRACT(EPOCH FROM (h.date_fin_traitement - h.date_debut_traitement)) / 60.0 BETWEEN 1 AND 180
    """)
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {"assistant_id": assistant_id, "service_id": service_id, "days": days}
        ).mappings().all()
    return rows


def get_active_assistant_count_for_service(service_id):
    # version simple : nombre d'assistants distincts ayant déjà traité ce service récemment
    query = text("""
        SELECT COUNT(DISTINCT h.assistant_id) AS nb
        FROM pharmacy_queue_history h
        WHERE h.service_id = :service_id
          AND h.ticket_id IS NOT NULL
          AND h.date_debut_traitement IS NOT NULL
          AND h.date_fin_traitement IS NOT NULL
          AND h.date_fin_traitement >= NOW() - INTERVAL '30 days'
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"service_id": service_id}).mappings().first()
    return int(row["nb"] or 0)


def predict_rf(service_id, assistant_id, file_id, mode_rattachement, poste_number,
               hour, minute, weekday, month, weekend, duree_defaut):
    try:
        model = joblib.load(MODEL_PATH)
    except Exception:
        return None

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
        "dure_estimee_par_defaut": duree_defaut,
    }])

    try:
        pred = model.predict(sample)[0]
        return float(pred)
    except Exception:
        return None


# ============================================================
# FINAL HYBRID ESTIMATION
# ============================================================

def get_final_estimation(
    service_id,
    assistant_id=None,
    mode_rattachement="manuel",
    poste_number="P1",
    hour=10,
    minute=0,
    weekday=2,
    month=4,
):
    service = get_service_info(service_id)
    if not service:
        return {
            "duration": 15.0,
            "method": "default_no_service",
            "detail": "Service introuvable.",
        }

    duree_defaut = float(service["dure_estimee_par_defaut"] or 15.0)
    file_id = service["queue_id"]

    weekend = 1 if weekday >= 5 else 0

    # ---------------------------
    # 1) moyenne service pondérée
    # ---------------------------
    service_rows = get_service_history(service_id, days=30)
    service_values = [
        {
            "duration": float(r["duration_min"]),
            "weight": get_recency_weight(float(r["age_days"] or 0)),
        }
        for r in service_rows
    ]
    moyenne_service = weighted_average(service_values)
    nb_hist_service = len(service_values)

    if nb_hist_service < 5 or not moyenne_service:
        return {
            "duration": round(duree_defaut, 2),
            "method": "default_duration_only",
            "detail": f"Historique service insuffisant ({nb_hist_service}).",
        }

    # confiance progressive
    confidence_service = min(1.0, nb_hist_service / 30.0)
    base_service = ((1.0 - confidence_service) * duree_defaut) + (confidence_service * moyenne_service)

    # ---------------------------
    # 2) facteur assistant
    # ---------------------------
    facteur_assistant = 1.0
    nb_hist_assistant = 0
    moyenne_assistant = 0.0

    if assistant_id:
        assistant_rows = get_assistant_service_history(assistant_id, service_id, days=30)
        assistant_values = [
            {
                "duration": float(r["duration_min"]),
                "weight": get_recency_weight(float(r["age_days"] or 0)),
            }
            for r in assistant_rows
        ]
        nb_hist_assistant = len(assistant_values)
        moyenne_assistant = weighted_average(assistant_values)

        if nb_hist_assistant >= 5 and moyenne_assistant > 0 and moyenne_service > 0:
            raw_factor = moyenne_assistant / moyenne_service
            facteur_assistant = clamp(raw_factor, 0.75, 1.25)

    # ---------------------------
    # 3) facteur temps
    # ---------------------------
    facteur_temps = compute_time_factor(hour, weekday, month)

    # ---------------------------
    # 4) facteur nb assistants
    # ---------------------------
    nb_assistants = get_active_assistant_count_for_service(service_id)
    facteur_nb_assistants = compute_assistant_count_factor(nb_assistants)

    # ---------------------------
    # 5) estimation métier
    # ---------------------------
    estimation_metier = (
        base_service
        * facteur_assistant
        * facteur_temps
        * facteur_nb_assistants
    )

    # ---------------------------
    # 6) RF
    # ---------------------------
    rf_pred = predict_rf(
        service_id=service_id,
        assistant_id=assistant_id,
        file_id=file_id,
        mode_rattachement=mode_rattachement,
        poste_number=poste_number,
        hour=hour,
        minute=minute,
        weekday=weekday,
        month=month,
        weekend=weekend,
        duree_defaut=duree_defaut,
    )

    if rf_pred is not None:
        # borne RF autour de l’estimation métier
        rf_pred = clamp(rf_pred, estimation_metier * 0.70, estimation_metier * 1.30)
        final_duration = (0.6 * estimation_metier) + (0.4 * rf_pred)
        method = "hybrid_business_plus_rf"
    else:
        final_duration = estimation_metier
        method = "business_only"

    # bornes finales sécurité
    min_safe = max(1.0, duree_defaut * 0.5)
    max_safe = max(min_safe, duree_defaut * 1.8)
    final_duration = clamp(final_duration, min_safe, max_safe)

    return {
        "duration": round(final_duration, 2),
        "method": method,
        "detail": {
            "duree_defaut": round(duree_defaut, 2),
            "moyenne_service": round(moyenne_service, 2),
            "nb_hist_service": nb_hist_service,
            "moyenne_assistant": round(moyenne_assistant, 2) if moyenne_assistant else 0.0,
            "nb_hist_assistant": nb_hist_assistant,
            "facteur_assistant": round(facteur_assistant, 3),
            "facteur_temps": round(facteur_temps, 3),
            "nb_assistants": nb_assistants,
            "facteur_nb_assistants": round(facteur_nb_assistants, 3),
            "base_service": round(base_service, 2),
            "estimation_metier": round(estimation_metier, 2),
            "rf_prediction": round(rf_pred, 2) if rf_pred is not None else None,
        }
    }




if __name__ == "__main__":
    tests = [
        {"service_id": 22, "assistant_id": 2, "hour": 10, "minute": 0, "weekday": 2, "month": 4},
        {"service_id": 23, "assistant_id": 12, "hour": 9, "minute": 30, "weekday": 1, "month": 4},
        {"service_id": 240, "assistant_id": 12, "hour": 11, "minute": 0, "weekday": 3, "month": 4},
    ]

    for idx, t in enumerate(tests, start=1):
        result = get_final_estimation(**t)
        print(f"\n--- TEST {idx} ---")
        print(result)