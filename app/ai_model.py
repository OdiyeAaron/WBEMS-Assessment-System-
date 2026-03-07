# app/ai_model.py

from . import db
# FIXED IMPORT: Using the new models for the latest score and historical records
from .models import Student, Attendance, Participation, LatestCompetenceScore, CompetenceScoreRecord
from datetime import datetime, date, timedelta
from flask import current_app as app
import numpy as np
import pandas as pd 
import pickle
import os

# --- Configuration ---
# Model path must match the output of train_model.py
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ml_models', 'competence_predictor.pkl')
PREDICTOR_MODEL = None

# --- HIRE System Thresholds ---
ACADEMIC_WEIGHT = 0.50
ATTENDANCE_WEIGHT = 0.30
PARTICIPATION_WEIGHT = 0.20

ATTENDANCE_THRESHOLD = 75.0  # 75%
ACADEMIC_THRESHOLD = 65.0    # 65%
COMPETENCE_THRESHOLD = 60.0  # 60%
PARTICIPATION_THRESHOLD = 5.0 # 5.0 rating

# --- ML Functions (No changes required here, logic is sound) ---

def load_model():
    """Attempts to load the pickled ML model."""
    global PREDICTOR_MODEL
    # Only attempt to load if not already loaded or if a previous attempt failed
    if PREDICTOR_MODEL is None or isinstance(PREDICTOR_MODEL, str):
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, 'rb') as file:
                    PREDICTOR_MODEL = pickle.load(file)
                print(f"INFO: Successfully loaded ML model from {MODEL_PATH}")
            except Exception as e:
                print(f"ERROR: Could not load ML model: {e}")
                PREDICTOR_MODEL = 'MODEL_ERROR'
        else:
            PREDICTOR_MODEL = 'MODEL_MISSING'
    return PREDICTOR_MODEL

def get_ml_prediction(academic_score, attendance_rate, participation_avg):
    """
    Uses the loaded Logistic Regression model to predict if a student is 'At-Risk'.
    """
    model = load_model()

    if isinstance(model, str):
        return {
            'risk_status': 'N/A',
            'details': f'Prediction Model Status: {model.replace("_", " ")}'
        }
    
    # Prepare the input data point as a DataFrame for scikit-learn
    input_data = pd.DataFrame([[academic_score, attendance_rate, participation_avg]],
                              columns=['academic_performance', 'attendance_rate', 'avg_participation_rating'])

    # Predict the classification (0: Not At-Risk, 1: At-Risk)
    prediction = model.predict(input_data)[0]

    # Predict the probability (Probability of At-Risk, class 1)
    if hasattr(model, 'predict_proba'):
        probability = model.predict_proba(input_data)[0][1] 
    else:
        probability = 0.5 # Default if predict_proba is missing

    if prediction == 1:
        risk_status = 'HIGH RISK'
        details = f'Predicted probability of At-Risk: {probability*100:.1f}%'
    else:
        risk_status = 'LOW RISK'
        details = f'Predicted probability of At-Risk: {probability*100:.1f}%'

    return {
        'risk_status': risk_status,
        'details': details
    }


# --- HIRE System Logic (Refined for Actionable Feedback) ---

def holistic_intervention_reasoning(competence_score, attendance_rate, participation_avg, academic_score, ml_risk_status):
    """
    Synthesizes multiple metrics, including the ML prediction, to provide a 
    prioritized intervention plan and more specific root cause analysis.
    """
    # Initialize with LOW priority
    priority_level = "LOW"
    root_cause = "All metrics are satisfactory."
    suggested_action = "Continue positive reinforcement and monitor progress quarterly."
    
    # Identify the weakest core metric (by score percentage contribution)
    # The lowest contributing score helps determine the most appropriate intervention focus.
    score_contributions = {
        # FIX: Use the 'academic_score' parameter instead of the undefined 'student.academic_performance'
        'Academic Performance': academic_score * ACADEMIC_WEIGHT, 
        'Attendance Rate': attendance_rate * ATTENDANCE_WEIGHT,
        'Participation Rating': (participation_avg * 10) * PARTICIPATION_WEIGHT
    }
    weakest_metric = min(score_contributions, key=score_contributions.get)

    # --- 1. CRITICAL Risk Checks (Highest Priority) ---
    if competence_score < COMPETENCE_THRESHOLD:
        priority_level = "CRITICAL"
        root_cause = f"Overall Competence Score ({competence_score:.1f}%) is critically low. Weakest metric: {weakest_metric}."
        suggested_action = "Mandatory meeting with Dean/Administrator and immediate parental contact. Enrollment in Remedial Program."
    
    # --- 2. HIGH Risk Checks ---
    elif ml_risk_status == 'HIGH RISK': 
        priority_level = "HIGH"
        root_cause = f"AI Model Prediction: Logistic Regression model flags the student as HIGH RISK for failure. Weakest metric: {weakest_metric}."
        suggested_action = "Schedule mandatory Counseling Session immediately, focusing on time management and study habits."
    elif attendance_rate < ATTENDANCE_THRESHOLD:
        priority_level = "HIGH"
        root_cause = f"Attendance rate ({attendance_rate:.1f}%) is below the institutional threshold of {ATTENDANCE_THRESHOLD:.1f}%."
        suggested_action = "Issue Formal Attendance Warning to Student and Guardian. Require check-ins before every class."
    elif academic_score < ACADEMIC_THRESHOLD:
        priority_level = "HIGH"
        root_cause = f"Academic Performance ({academic_score:.1f}%) is below {ACADEMIC_THRESHOLD:.1f}% benchmark."
        suggested_action = "Assign personalized remedial study resources and mandatory weekly tutoring sessions."
    
    # --- 3. MEDIUM Risk Checks ---
    elif participation_avg < PARTICIPATION_THRESHOLD:
        priority_level = "MEDIUM"
        root_cause = f"Participation rating ({participation_avg:.1f}) is consistently low (below {PARTICIPATION_THRESHOLD:.1f})."
        suggested_action = "Encourage participation by assigning specific, low-stakes class activities/presentations."

    # --- 4. Generate Prioritized Actions (already handled above) ---

    return {
        'priority': priority_level, 
        'root_cause': root_cause, 
        'suggested_action': suggested_action
    }

# --- Main Competence Calculation (No changes needed, the call is correct) ---

def compute_competence_for_student(student_id):
    """
    Calculates the student's competence score and runs the HIRE analysis.
    UPDATED: Now handles saving both the historical record and the latest score.
    """
    student = Student.query.get(student_id)
    if not student:
        return {'error': 'Student not found'}

    # 1. Fetch Metrics
    attendance_records = Attendance.query.filter_by(student_id=student_id).all()
    participation_records = Participation.query.filter_by(student_id=student_id).all()

    # 2. Calculate Attendance Rate
    total_records = len(attendance_records)
    if total_records > 0:
        present_count = len([r for r in attendance_records if r.status and r.status.lower() == 'present'])
        attendance_percent = present_count / total_records
        attendance_rate_percent = attendance_percent * 100.0
    else:
        # Default to 50% if no records helps prevent zero division/extreme scores early on
        attendance_percent = 0.5 
        attendance_rate_percent = 50.0

    # 3. Calculate Average Participation Rating (0-10)
    if participation_records:
        ratings = [r.rating for r in participation_records]
        participation_avg = np.mean(ratings) if ratings else 0.0
    else:
        participation_avg = 0.0

    # 4. Calculate Final Competence Score (Out of 100)
    normalized_participation = participation_avg * 10 
    
    final_score = (
        (student.academic_performance * ACADEMIC_WEIGHT) + 
        (attendance_rate_percent * ATTENDANCE_WEIGHT) +
        (normalized_participation * PARTICIPATION_WEIGHT)
    )

    # Determine Grade
    if final_score >= 80:
        grade = 'Excellent'
    elif final_score >= 70:
        grade = 'Good'
    elif final_score >= 60:
        grade = 'Satisfactory'
    else:
        grade = 'Needs Improvement'

    # 5. ML-POWERED PREDICTION 
    ml_result = get_ml_prediction(
        academic_score=student.academic_performance,
        attendance_rate=attendance_rate_percent, 
        participation_avg=participation_avg      
    )
    
    # 6. HIRE ANALYSIS (Pass ML Risk)
    # The academic_score is correctly passed here to resolve the NameError
    hire_analysis = holistic_intervention_reasoning(
        competence_score=final_score,
        attendance_rate=attendance_rate_percent, 
        participation_avg=participation_avg, 
        academic_score=student.academic_performance,
        ml_risk_status=ml_result['risk_status']
    )

    # 7. Update/Store CompetenceScore 
    
    # A. Save Historical Record (for trend chart)
    history_record = CompetenceScoreRecord(
        student_id=student_id, 
        score=final_score, 
        calculated_at=datetime.utcnow()
    )
    db.session.add(history_record)

    # B. Update/Insert Latest Score (for quick dashboard lookup)
    latest_score = LatestCompetenceScore.query.filter_by(student_id=student_id).first()
    
    if latest_score:
        # Update existing record
        latest_score.score = final_score
        latest_score.grade = grade
        # The 'updated_at' column is handled automatically by SQLAlchemy
    else:
        # Create a new record
        latest_score = LatestCompetenceScore(
            student_id=student_id,
            score=final_score,
            grade=grade
        )
        db.session.add(latest_score) 
        
    db.session.commit()
    
    # Return all calculated data for the dashboard
    return {
        'competence': latest_score, # Return the latest score object
        'academic_score': student.academic_performance,
        'attendance_rate': attendance_rate_percent,
        'participation_avg': participation_avg,
        'ml_result': ml_result, 
        'hire_analysis': hire_analysis
    }