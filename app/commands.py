# app/commands.py

import click
from faker import Faker
from random import randint, choice, uniform
from datetime import datetime, timedelta, date

from . import db
# FIXED IMPORT: Using the new models for latest score and historical records
from .models import User, Student, Activity, Attendance, Participation, LatestCompetenceScore, CompetenceScoreRecord
from .ai_model import compute_competence_for_student
from werkzeug.security import generate_password_hash
from flask import current_app as app
from sqlalchemy import text  

# --- CORE SETUP FUNCTION (Called by CLI) ---

def seed_data(num_students=500, mixed_performance=True):
    """Generates students and populates their records."""
    fake = Faker()

    click.echo(f"Starting database population for {num_students} students...")
    
    # 1. Create Activities if none exist
    activities = Activity.query.all()
    if not activities:
        click.echo("Creating initial activities...")
        db.session.add(Activity(name="Coding Club", category="Academic", description="Python/Web Dev"))
        db.session.add(Activity(name="Debate Team", category="Co-Curricular", description="Public Speaking"))
        db.session.add(Activity(name="Soccer Team", category="Sports", description="Physical Fitness"))
        db.session.commit()
        activities = Activity.query.all()
        
    activity_ids = [a.id for a in activities]
    
    # 2. Define courses and initial student creation lists
    new_students = []
    courses = ['Computer Science', 'Data Analytics', 'Mechanical Engineering', 'Business', 'Arts']
    
    for i in range(1, num_students + 1):
        name = fake.name()
        level = choice(['Year 1', 'Year 2', 'Year 3', 'Year 4'])
        course = choice(courses)
        
        if mixed_performance:
            # Random scores between 55 and 95 (Mixed performance)
            academic_performance = round(uniform(55.0, 95.0), 1) 
        else:
            # Low scores for HIRE test (40.0 - 60.0)
            academic_performance = round(uniform(40.0, 60.0), 1)

        student = Student(
            name=name, 
            level=level, 
            course=course, 
            academic_performance=academic_performance
        )
        new_students.append(student)

        if i % 100 == 0:
            db.session.bulk_save_objects(new_students)
            new_students = []

    db.session.bulk_save_objects(new_students)
    db.session.commit()
    click.echo(f"✅ All {num_students} students successfully created.")
    
    # 3. Generate Records
    all_students = Student.query.all()
    click.echo("Generating random attendance and participation records...")
    
    for student in all_students:
        
        num_attendance = randint(10, 30)
        start_date = date.today() - timedelta(days=90)
        
        for _ in range(num_attendance):
            random_date = start_date + timedelta(days=randint(1, 90))
            # Random attendance: 3/4 present, 1/4 absent
            status = choice(['present', 'present', 'present', 'absent']) 
            
            db.session.add(Attendance(
                student_id=student.id, 
                date=random_date, 
                status=status
            ))

        num_participation = randint(5, 15)
        for _ in range(num_participation):
            rating = round(uniform(3.0, 9.9), 1)
            
            db.session.add(Participation(
                student_id=student.id,
                activity_id=choice(activity_ids),
                rating=rating,
                timestamp=datetime.utcnow() - timedelta(days=randint(1, 90))
            ))
            
        # 4. Generate Historical Scores for Trend Chart (NEW LOGIC)
        # Create 3 fake historical scores before the final calculation
        for j in range(1, 4):
            # Generate a slightly varied score for history
            historical_score = round(uniform(student.academic_performance - 10, student.academic_performance + 5), 1)
            historical_score = max(50.0, min(95.0, historical_score)) # Keep scores reasonable
            
            # Timestamp the score in the past
            past_date = datetime.utcnow() - timedelta(days=90 - (j * 15))
            
            db.session.add(CompetenceScoreRecord(
                student_id=student.id,
                score=historical_score,
                calculated_at=past_date
            ))
            
        # 5. Compute the FINAL Competence Score (which saves the latest score AND the last history record)
        compute_competence_for_student(student.id)
        
    db.session.commit()
    click.echo("✅ All records and competence scores computed (including historical data).")
    click.echo("Database population complete!")

# --- 1. Master Setup Command ---

@app.cli.command("setup-database")
@click.argument('num_students', type=int, default=500)
def setup_database(num_students):
    """Deletes existing data, creates tables, sets up Admin user, and seeds data."""
    
    click.echo("\n--- STARTING FULL DATABASE SETUP ---")
    
    # 1. Clean up and setup tables
    click.echo("1. Deleting all tables and creating fresh database...")
    db.drop_all()
    db.create_all()
    
    # 2. Create Admin User
    click.echo("2. Creating Admin user (admin/1234)...")
    admin_user = User(username='admin', email='admin@example.com', role='Admin')
    admin_user.password_hash = generate_password_hash('1234')
    db.session.add(admin_user)
    db.session.commit()
    
    # 3. Seed Data
    click.echo(f"3. Seeding {num_students} students with mixed data...")
    seed_data(num_students=num_students, mixed_performance=True)
    
    click.echo("\n--- SETUP COMPLETE: LOGIN AS admin/1234 ---")


# --- 2. User Creation Commands ---

@app.cli.command("create-user")
@click.argument("username")
@click.argument("password")
@click.argument("role") 
def create_user(username, password, role):
    """Create a new user: flask create-user teacher pass lecturer"""
    if role.lower() not in ['admin', 'lecturer']:
        click.echo("Invalid role. Must be 'admin' or 'lecturer'.")
        return

    with app.app_context():
        if User.query.filter_by(username=username).first():
            click.echo("User exists.")
            return
        
        user = User(username=username, email=f"{username}@example.com", 
                    password_hash=generate_password_hash(password),
                    role=role.capitalize())
        db.session.add(user)
        db.session.commit()
        click.echo(f"User '{username}' with role '{role.capitalize()}' created.")

# --- 3. Data Management Group (Refactored) ---

@app.cli.group()
def data():
    """Commands for managing dummy data."""
    pass

@data.command()
@click.argument('num_students', type=int)
def generate_all(num_students):
    """Generates NUM_STUDENTS students and populates their records (mixed performance)."""
    seed_data(num_students=num_students, mixed_performance=True)
    
@data.command()
@click.argument('num_students', type=int)
def generate_low_risk(num_students):
    """Generates NUM_STUDENTS students designed to fail (CRITICAL HIRE trigger)."""
    
    fake = Faker()
    click.echo(f"Starting creation of {num_students} LOW-RISK test students...")

    # 1. Create Activities if none exist (using the common seed_data logic)
    activities = Activity.query.all()
    if not activities:
        click.echo("Creating initial activities...")
        db.session.add(Activity(name="Coding Club", category="Academic", description="Python/Web Dev"))
        db.session.add(Activity(name="Debate Team", category="Co-Curricular", description="Public Speaking"))
        db.session.add(Activity(name="Soccer Team", category="Sports", description="Physical Fitness"))
        db.session.commit()
        activities = Activity.query.all()
    activity_ids = [a.id for a in activities]
    
    # 2. Create Low-Risk Students
    new_students = []
    for i in range(num_students):
        name = f"LowRisk {i+1} {fake.last_name()}"
        # Force Academic Performance to be low (40.0 - 60.0)
        academic_performance = round(uniform(40.0, 60.0), 1) 
        
        student = Student(
            name=name, 
            level="Test Level", 
            course="HIRE Test Subject", 
            academic_performance=academic_performance
        )
        new_students.append(student)

    db.session.bulk_save_objects(new_students)
    db.session.commit()
    click.echo(f"  ... {num_students} students created with low scores.")
    
    # 3. Generate Low Records
    all_students = Student.query.filter(Student.name.startswith("LowRisk")).all()
    click.echo("Generating low attendance (20%) and low participation records...")
    
    for student in all_students:
        
        num_attendance = 20 # fixed number of records
        start_date = date.today() - timedelta(days=60)
        
        for i in range(num_attendance):
            # Force LOW attendance: 80% absent, 20% present
            status = choice(['absent'] * 8 + ['present'] * 2) 
            
            db.session.add(Attendance(
                student_id=student.id, 
                date=start_date + timedelta(days=i), 
                status=status
            ))

        num_participation = 10
        for _ in range(num_participation):
            # Force LOW participation rating (2.0 - 5.0 out of 10)
            rating = round(uniform(2.0, 5.0), 1) 
            
            db.session.add(Participation(
                student_id=student.id,
                activity_id=choice(activity_ids),
                rating=rating,
                timestamp=datetime.utcnow() - timedelta(days=randint(1, 60))
            ))
            
        # 4. Generate Historical Scores for Trend Chart (NEW LOGIC)
        for j in range(1, 4):
            # Generate a slightly varied score for history
            historical_score = round(uniform(student.academic_performance - 10, student.academic_performance + 5), 1)
            historical_score = max(50.0, min(95.0, historical_score))
            
            # Timestamp the score in the past
            past_date = datetime.utcnow() - timedelta(days=60 - (j * 10))
            
            db.session.add(CompetenceScoreRecord(
                student_id=student.id,
                score=historical_score,
                calculated_at=past_date
            ))
            
        # 5. Compute the FINAL Competence Score
        compute_competence_for_student(student.id)
        
    db.session.commit()
    click.echo("✅ HIRE Test Students created and scores computed. Ready for verification.")