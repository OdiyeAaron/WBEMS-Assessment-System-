from datetime import datetime
from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
# Assuming 'db' is imported correctly as 'app.db' when the app starts

# --- User Model ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True) 
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(64), default='Lecturer') # Admin or Lecturer

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- Student Model ---
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    
    # Detailed Student Information Fields
    reg_number = db.Column(db.String(50), unique=True, nullable=True)
    dob = db.Column(db.Date, nullable=True)
    academic_group = db.Column(db.String(120), nullable=True)
    academic_year = db.Column(db.String(50), nullable=True)
    academic_semester_term = db.Column(db.String(50), nullable=True)
    photo_url = db.Column(db.String(300), nullable=True)
    
    # Core Competence Fields
    level = db.Column(db.String(50), nullable=True)
    course = db.Column(db.String(120), nullable=True)
    academic_performance = db.Column(db.Float, default=60.0)

    # Relationships
    participations = db.relationship('Participation', backref='student', lazy='dynamic')
    attendance_records = db.relationship('Attendance', backref='student', lazy='dynamic')
    # CHANGED: competence_records now links to the historical table
    competence_records = db.relationship('CompetenceScoreRecord', backref='student', lazy='dynamic') 
    # NEW: Link to the latest score for easy lookup
    latest_score = db.relationship('LatestCompetenceScore', backref='student', uselist=False) 

# --- Activity Model ---
class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    description = db.Column(db.String(300), nullable=True)
    
    participations = db.relationship('Participation', backref='activity', lazy='dynamic')

# --- Participation Model ---
class Participation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'))
    rating = db.Column(db.Float, nullable=False, default=5.0)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    
# --- Attendance Model ---
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    date = db.Column(db.Date, index=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)

# --- COMPETENCE SCORE MODELS (UPDATED FOR TRENDS) ---

# 1. Historical Model: Stores every competence score calculation over time
class CompetenceScoreRecord(db.Model):
    __tablename__ = 'competence_score_record'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    score = db.Column(db.Float, default=0.0)
    # NEW: We need to know WHEN the score was calculated
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow, index=True) 

# 2. Latest Score Model: A simple table to hold the current, active score (replaces the old single table)
class LatestCompetenceScore(db.Model):
    __tablename__ = 'latest_competence_score'
    id = db.Column(db.Integer, primary_key=True)
    # Changed to unique=True to ensure only one current score per student
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), unique=True) 
    score = db.Column(db.Float, default=0.0)
    grade = db.Column(db.String(10), default='E')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)