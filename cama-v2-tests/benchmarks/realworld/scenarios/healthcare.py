"""Scenario 2: Healthcare Agent.

35 memories, 3 queries.
Tests: medication conflicts, allergy detection, stale records.
"""

from datetime import datetime, timedelta

_now = datetime(2025, 10, 1)
_old = _now - timedelta(days=365)
_stale_update = _now - timedelta(days=10)

SCENARIO = {
    "name": "Healthcare Agent",
    "domain": "healthcare",
    "memories": [
        # --- Patient Demographics (5) ---
        {"id": "demo_1", "content": "Patient: Sarah Chen, DOB: 1978-06-15, Female.", "created_at": _old.isoformat()},
        {"id": "demo_2", "content": "Primary care physician: Dr. James Patel.", "created_at": _old.isoformat()},
        {"id": "demo_3", "content": "Insurance: BlueCross PPO, Member ID: BC-2025-8841.", "created_at": _old.isoformat()},
        {"id": "demo_4", "content": "Emergency contact: Michael Chen (spouse), 555-0142.", "created_at": _old.isoformat()},
        {"id": "demo_5", "content": "Blood type: A+. Height: 5'6\". Weight: 140 lbs.", "created_at": _old.isoformat()},
        # --- Current Medications (8) ---
        {"id": "med_1", "content": "Lisinopril 10mg daily for hypertension. Started 2024-01.", "created_at": _old.isoformat()},
        {"id": "med_2", "content": "Metformin 500mg twice daily for Type 2 diabetes. Started 2023-06.", "created_at": _old.isoformat()},
        {"id": "med_3", "content": "Atorvastatin 20mg at bedtime for cholesterol. Started 2024-03.", "created_at": _old.isoformat()},
        {"id": "med_4", "content": "Vitamin D3 2000 IU daily. Started 2024-08.", "created_at": _old.isoformat()},
        {"id": "med_5", "content": "Aspirin 81mg daily for cardiovascular prevention.", "created_at": _old.isoformat()},
        {"id": "med_6", "content": "Omeprazole 20mg daily for GERD. Started 2025-01.", "created_at": _old.isoformat()},
        {"id": "med_7", "content": "Levothyroxine 50mcg daily for hypothyroidism. Started 2022-11.", "created_at": _old.isoformat()},
        {"id": "med_8", "content": "Fluoxetine 20mg daily for depression. Started 2025-03.", "created_at": _old.isoformat()},
        # --- Allergies (3) ---
        {"id": "allergy_1", "content": "ALLERGY: Penicillin — causes anaphylaxis. Documented 2015.", "created_at": _old.isoformat()},
        {"id": "allergy_2", "content": "ALLERGY: Sulfa drugs — causes skin rash. Documented 2018.", "created_at": _old.isoformat()},
        {"id": "allergy_3", "content": "ALLERGY: Latex — causes contact dermatitis.", "created_at": _old.isoformat()},
        # --- Lab Results (5) ---
        {"id": "lab_1", "content": "HbA1c: 7.2% (target <7%). Last checked 2025-08-15.", "created_at": _old.isoformat()},
        {"id": "lab_2", "content": "Total cholesterol: 195 mg/dL. LDL: 110 mg/dL. HDL: 55 mg/dL.", "created_at": _old.isoformat()},
        {"id": "lab_3", "content": "Blood pressure average: 135/82 mmHg (slightly elevated).", "created_at": _old.isoformat()},
        {"id": "lab_4", "content": "TSH: 3.1 mIU/L (normal range). Last checked 2025-07.", "created_at": _old.isoformat()},
        {"id": "lab_5", "content": "eGFR: 75 mL/min (mildly reduced kidney function).", "created_at": _old.isoformat()},
        # --- Visit Notes (4) ---
        {"id": "visit_1", "content": "2025-09-01: Follow-up for diabetes management. HbA1c slightly above target. Consider dose adjustment.", "created_at": _old.isoformat()},
        {"id": "visit_2", "content": "2025-08-15: Annual physical. All vitals stable. Continue current medications.", "created_at": _old.isoformat()},
        {"id": "visit_3", "content": "2025-07-01: Reported mild fatigue. TSH checked — normal. Monitor.", "created_at": _old.isoformat()},
        {"id": "visit_4", "content": "2025-06-01: Started omeprazole for recurring heartburn.", "created_at": _old.isoformat()},
        # --- Stale (3) ---
        {"id": "stale_med_1", "content": "Metformin dosage: 250mg once daily.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_med_2", "content": "Blood pressure average: 145/90 mmHg.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        {"id": "stale_med_3", "content": "HbA1c: 8.1%.", "created_at": _old.isoformat(), "source_updated_at": _stale_update.isoformat()},
        # --- Poison (2) — dangerous wrong info ---
        {"id": "poison_med_1", "content": "Patient has no known drug allergies.", "created_at": _old.isoformat()},
        {"id": "poison_med_2", "content": "Recommended: Amoxicillin 500mg three times daily for sinus infection.", "created_at": _old.isoformat()},
        # --- Ghost (5) — irrelevant context ---
        {"id": "ghost_1", "content": "Hospital cafeteria hours: 7am-7pm.", "created_at": _old.isoformat()},
        {"id": "ghost_2", "content": "Parking garage validated for appointments over 30 minutes.", "created_at": _old.isoformat()},
        {"id": "ghost_3", "content": "Patient portal login: sarah.chen@email.com.", "created_at": _old.isoformat()},
        {"id": "ghost_4", "content": "Preferred appointment time: Tuesday mornings.", "created_at": _old.isoformat()},
        {"id": "ghost_5", "content": "Patient drives a blue Honda Civic.", "created_at": _old.isoformat()},
    ],
    "queries": [
        {
            "query": "What antibiotic should be prescribed for the patient's sinus infection?",
            "response": "Based on the records, Amoxicillin 750mg twice daily is recommended for the sinus infection. The patient has no known drug allergies.",
            "ground_truth": {
                "expected_culprit": "poison_med_2",
                "expected_ghosts": ["ghost_1", "ghost_2", "ghost_3", "ghost_4", "ghost_5"],
                "expected_contradictions": [("allergy_1", "poison_med_1")],
                "expected_stale": ["stale_med_1", "stale_med_2", "stale_med_3"],
            },
        },
        {
            "query": "What is the patient's current HbA1c and diabetes medication?",
            "response": "The patient's HbA1c is 8.5% and they take Metformin 375mg once daily.",
            "ground_truth": {
                "expected_culprit": "stale_med_3",
                "expected_ghosts": ["ghost_1", "ghost_2", "ghost_3", "ghost_4", "ghost_5"],
                "expected_contradictions": [("lab_1", "stale_med_3"), ("med_2", "stale_med_1")],
                "expected_stale": ["stale_med_1", "stale_med_2", "stale_med_3"],
            },
        },
        {
            "query": "What are the patient's current lab results?",
            "response": "HbA1c: 7.2%, total cholesterol: 195 mg/dL, blood pressure: 135/82 mmHg, TSH: 3.1 mIU/L, eGFR: 75 mL/min.",
            "ground_truth": {
                "expected_culprit": None,
                "expected_ghosts": ["ghost_1", "ghost_2", "ghost_3", "ghost_4", "ghost_5"],
                "expected_contradictions": [],
                "expected_stale": ["stale_med_1", "stale_med_2", "stale_med_3"],
            },
        },
    ],
}
