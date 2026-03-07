# create_dummy_model.py

import pandas as pd
import numpy as np
import pickle
from sklearn.linear_model import LinearRegression
import os

# --- 1. Define the Data (Must match the features used in app/ai_model.py) ---
# Features: Academic Score, Attendance Rate, Participation Count, Participation Avg Rating
data = {
    'academic_score': [90, 85, 70, 55, 95],
    'attendance_rate': [0.95, 0.80, 0.60, 0.99, 0.50],
    'participation_count': [10, 5, 2, 8, 1],
    'participation_avg': [9.0, 7.0, 4.0, 8.5, 3.0]
}
X = pd.DataFrame(data)

# Target: A fictional "future success score" (0 to 100)
# This is a simple calculation based on the features to create a plausible output.
y = (X['academic_score'] * 0.4) + (X['attendance_rate'] * 30) + (X['participation_avg'] * 3)

# --- 2. Train a Simple Linear Model ---
# We use Linear Regression for simplicity, as it can be pickled easily.
model = LinearRegression()
model.fit(X, y)

# --- 3. Save the Model to the Correct Location ---
# The location must be 'app/ml_models/competence_predictor.pkl'
model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'ml_models')
model_path = os.path.join(model_dir, 'competence_predictor.pkl')

# Ensure the ml_models directory exists
if not os.path.exists(model_dir):
    os.makedirs(model_dir)

# Save the trained model using pickle
with open(model_path, 'wb') as file:
    pickle.dump(model, file)

print(f"✅ Dummy ML model created and saved successfully to: {model_path}")
print("You can now run your Flask application!")