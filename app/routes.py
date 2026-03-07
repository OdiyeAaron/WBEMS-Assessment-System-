from flask import render_template, request, jsonify, redirect, url_for, flash, Response, abort, send_file # <-- Added send_file
from flask import current_app as app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import numpy as np
import pandas as pd
from io import BytesIO # <-- Changed from StringIO to BytesIO for binary data (Excel)
from sqlalchemy import func, select 

# IMPORTANT: UPDATED IMPORTS based on models.py changes
from . import db
from .models import Student, Activity, Attendance, Participation, LatestCompetenceScore, CompetenceScoreRecord
from .ai_model import compute_competence_for_student


# --- UTILITY FUNCTION: Course Averages (Helper for comparison chart) ---

def get_course_averages(student_id):
    """Calculates the average Academic Performance and Competence Score for a student's course."""
    
    # 1. Get the current student's course
    student = Student.query.get(student_id)
    if not student:
        return {'course_avg_academic': 0.0, 'course_avg_competence': 0.0}
        
    course = student.course
    
    # 2. Calculate the average metrics for that entire course
    course_data = db.session.query(
        func.avg(Student.academic_performance).label('avg_academic'),
        func.avg(LatestCompetenceScore.score).label('avg_competence')
    ).join(LatestCompetenceScore, Student.id == LatestCompetenceScore.student_id).filter(
        Student.course == course
    ).first()
    
    if course_data.avg_academic is None:
        return {'course_avg_academic': 0.0, 'course_avg_competence': 0.0}

    # Returns a dictionary of averages
    return {
        'course_avg_academic': round(course_data.avg_academic, 1),
        'course_avg_competence': round(course_data.avg_competence, 1)
    }

# --- Role-Based Access Control (RBAC) Decorator ---
def role_required(role="Admin"):
    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            # 1. Check if the user is logged in
            if not current_user.is_authenticated:
                return app.login_manager.unauthorized() 

            # 2. Check if the user has the required role
            if current_user.role == role:
                return func(*args, **kwargs)
            
            # If logged in but unauthorized role
            flash(f"You do not have permission to access this resource. ({role} required).", 'danger')
            return redirect(url_for('dashboard')) 
        return decorated_view
    return wrapper
# ----------------------------------------------------


# --- Core Application Routes ---
@app.route('/')
@app.route('/dashboard')
@login_required 
def dashboard():
    total_students = Student.query.count()
    
    # Calculate average competence score across all students
    all_scores = LatestCompetenceScore.query.all() 
    avg_score = round(np.mean([s.score for s in all_scores]), 1) if all_scores else 0.0
    
    # Fetch low attendance count (You may need a more efficient query here)
    low_attendance_count = db.session.query(Student.id).join(Attendance).filter(Attendance.status == 'absent').distinct().count()

    total_attendance_records = Attendance.query.count()
    
    # --- FIX: Query scalar values and convert to dictionaries ---
    student_rows = db.session.query(
        Student.id, 
        Student.name,
        Student.course,
        Student.academic_performance,
        LatestCompetenceScore.score, 
        LatestCompetenceScore.grade,
        # NOTE: 'priority' needs to be calculated/derived if used in the template
    ).outerjoin(LatestCompetenceScore).order_by(Student.id).all()
    
    # Convert SQLAlchemy Row objects to a list of standard dictionaries
    student_details = []
    for row in student_rows:
        data = row._asdict()
        # Add 'academic_performance' and 'priority' based on current data
        data['academic_performance'] = round(data.get('academic_performance', 0.0), 1)
        data['priority'] = 'LOW' # Placeholder logic; implement real priority calculation if needed
        student_details.append(data)
    # --- END FIX ---

    # Renders the main dashboard.html
    return render_template('dashboard.html',
                           total_students=total_students,
                           low_attendance_count=low_attendance_count,
                           total_attendance_records=total_attendance_records,
                           student_details=student_details, # Now a list of dictionaries
                           avg_score=avg_score    
                            )

# Route for adding a student via form (RESTRICTED TO ADMIN)
@app.route('/add_student', methods=['POST'])
@login_required 
@role_required(role='Admin')
def add_student():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            level = request.form.get('level')
            course = request.form.get('course')
            academic_performance = float(request.form.get('academic_performance') or 60.0)

            s = Student(name=name, level=level, course=course, academic_performance=academic_performance)
            db.session.add(s)
            db.session.commit()
            flash(f'Student {name} added successfully!', 'success')

            compute_competence_for_student(s.id)

            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding student: {e}', 'danger')

    return redirect(url_for('dashboard'))

# Updated route for the individual student profile
@app.route('/student/<int:student_id>')
@login_required
def student_dashboard(student_id):
    student = Student.query.get_or_404(student_id)
    
    # CRITICAL: Run the single, comprehensive function which handles ML and HIRE
    analysis_data = compute_competence_for_student(student_id)
    
    if 'error' in analysis_data:
        flash(analysis_data['error'], 'danger')
        return redirect(url_for('dashboard'))

    # Fetch related data (Participation and Attendance for the history lists)
    try:
        participations = student.participations.order_by(Participation.timestamp.desc()).all()
        attendance_records = student.attendance_records.order_by(Attendance.date.desc()).all()
    except AttributeError:
        participations = student.participations.all()
        attendance_records = student.attendance_records.all()
        
    # --- FETCH: historical Competence Scores (Raw SQLAlchemy objects) ---
    # NOTE: Using the new historical table
    historical_scores = CompetenceScoreRecord.query.filter_by(student_id=student_id).order_by(CompetenceScoreRecord.calculated_at.asc()).all()
    
    # --- FETCH: Comparison Data for Chart ---
    course_averages = get_course_averages(student_id) # <-- NEW
    
    # --- Convert SQLAlchemy objects to JSON serializable dictionaries for Chart.js ---
    historical_scores_jsonable = [
        {
            'score': score.score,
            # We convert the datetime object to an ISO format string, which is serializable
            'calculated_at': score.calculated_at.isoformat() 
        } 
        for score in historical_scores
    ]
    
    # Extract data from the analysis result for template clarity
    competence = analysis_data['competence'] 
    attendance_percent = analysis_data['attendance_rate']
    avg_participation = analysis_data['participation_avg']
    ml_result = analysis_data['ml_result'] 
    hire_report = analysis_data['hire_analysis']
    
    # Renders the student_dashboard.html template
    return render_template('student_dashboard.html',
                           student=student,
                           participations=participations,
                           attendance_records=attendance_records,
                           competence=competence,
                           attendance_percent=round(attendance_percent, 1),
                           avg_participation=round(avg_participation, 1),
                           ml_result=ml_result,
                           hire_report=hire_report,
                           historical_scores=historical_scores_jsonable, # for Trend Chart
                           course_averages=course_averages # for Comparison Chart
                            )


# Route for updating student information (RESTRICTED TO ADMIN)
@app.route('/student/update/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(role='Admin')
def update_student_profile(student_id):
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        try:
            student.name = request.form.get('name')
            student.level = request.form.get('level')
            student.course = request.form.get('course')
            student.academic_performance = float(request.form.get('academic_performance') or 60.0)
            db.session.commit()
            
            compute_competence_for_student(student.id)
            
            flash(f'Profile for {student.name} updated successfully!', 'success')
            return redirect(url_for('student_dashboard', student_id=student.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {e}', 'danger')
            return redirect(url_for('update_student_profile', student_id=student.id))

    return render_template('update_profile.html', student=student)

# Route for Student Search 
@app.route('/search', methods=['GET'])
@login_required
def search_students():
    query = request.args.get('query', '')
    students = []
    
    if query:
        students = Student.query.filter(
            Student.name.ilike(f'%{query}%')
        ).all()
        
    # FIX: Ensure students list is also converted to dicts if search_students.html uses bracket notation
    students_dicts = [s.__dict__ for s in students] 
        
    return render_template('search_students.html', students=students_dicts, query=query)


# --- Data Export Route (Updated to export XLSX) ---
@app.route('/export_data') # Updated route URL for clarity
@login_required
@role_required(role='Admin')
def export_data(): # Updated function name
    # 1. Query Data
    students_with_scores = db.session.query(
        Student,
        LatestCompetenceScore
    ).outerjoin(LatestCompetenceScore).all()

    data = []
    for student, score in students_with_scores:
        # Recalculate attendance rate for the export file
        attendance_records = student.attendance_records.all()
        total_records = len(attendance_records)
        present_count = sum(1 for r in attendance_records if r.status and r.status.lower() == 'present')
        attendance_percent = round((present_count / total_records * 100), 1) if total_records > 0 else 0

        data.append({
            'Student ID': student.id,
            'Name': student.name,
            'Level': student.level,
            'Course': student.course,
            'Academic Performance (%)': student.academic_performance,
            'Attendance Rate (%)': attendance_percent,
            'Competence Score': round(score.score, 1) if score else 0.0,
            'Competence Grade': score.grade if score else 'N/A',
            'Profile_Picture_URL': getattr(student, 'profile_picture_url', '') # Retrieves photo URL safely
        })

    # 2. Create DataFrame
    df = pd.DataFrame(data)
    
    # 3. Create Excel File in Memory (BytesIO)
    excel_buffer = BytesIO() # Use BytesIO for binary data

    # Use pandas to save to the BytesIO object as XLSX (Requires openpyxl)
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='StudentData')
        
    excel_buffer.seek(0) # Rewind the buffer to the beginning

    # 4. Stream the File to the User
    return send_file(
        excel_buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name=f"student_data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        as_attachment=True
    )


# --- Records Management Hub ---
@app.route('/records_home')
@login_required
def records_home():
    activities = Activity.query.all()
    students = Student.query.all()
    return render_template('records_home.html', activities=activities, students=students)

# Route to Create New Activity (RESTRICTED TO ADMIN)
@app.route('/create_activity', methods=['POST'])
@login_required
@role_required(role='Admin')
def create_activity():
    try:
        name = request.form.get('activity_name')
        category = request.form.get('category')
        description = request.form.get('description')
        
        a = Activity(name=name, category=category, description=description)
        db.session.add(a)
        db.session.commit()
        flash(f'Activity "{name}" created successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating activity: {e}', 'danger')
        
    return redirect(url_for('records_home'))

# Route to Log Attendance (OPEN TO LECTURERS)
@app.route('/log_attendance', methods=['POST'])
@login_required
def log_attendance():
    try:
        student_id = request.form.get('student_id')
        date_str = request.form.get('date')
        status = request.form.get('status')
        
        if not student_id or not date_str or not status:
            flash('Missing data for attendance log.', 'danger')
            return redirect(url_for('records_home'))

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        a = Attendance(student_id=student_id, date=date_obj, status=status)
        db.session.add(a)
        db.session.commit()
        
        compute_competence_for_student(student_id)
        
        flash(f'Attendance logged for Student #{student_id} ({status}). Score updated.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error logging attendance: {e}', 'danger')
        
    return redirect(url_for('records_home'))

# Route to Log Participation (OPEN TO LECTURERS)
@app.route('/log_participation', methods=['POST'])
@login_required
def log_participation():
    try:
        student_id = request.form.get('student_id')
        activity_id = request.form.get('activity_id')
        rating = float(request.form.get('rating'))
        
        if not student_id or not activity_id or rating is None:
            flash('Missing data for participation log.', 'danger')
            return redirect(url_for('records_home'))
            
        p = Participation(student_id=student_id, activity_id=activity_id, rating=rating)
        db.session.add(p)
        db.session.commit()
        
        compute_competence_for_student(student_id)
        
        flash(f'Participation logged for Student #{student_id} with rating {rating}. Score updated.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error logging participation: {e}', 'danger')
        
    return redirect(url_for('records_home'))