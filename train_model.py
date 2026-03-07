import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
import pickle
import os

# --- 1. Define Paths and Constants ---
# This path must match the model loading path in app/ai_model.py
MODEL_DIR = os.path.join('app', 'ml_models')
MODEL_FILENAME = 'competence_predictor.pkl'
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)

# Create the directory if it doesn't exist
if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)
    print(f"Created directory: {MODEL_DIR}")

# --- 2. Generate Mock Data ---
# A small, synthetic dataset is created for demonstration purposes
np.random.seed(42)  # For reproducibility
N = 100  # Number of mock students

# Features used for prediction (must match the inputs you will provide)
data = {
    'academic_performance': np.random.randint(40, 95, N),   # Score 0-100
    'attendance_rate': np.random.randint(50, 100, N),        # Rate 0-100%
    'avg_participation_rating': np.random.uniform(3, 9.5, N).round(1) # Rating 0-10
}
df = pd.DataFrame(data)

# Target/Label: 'Predicted_At_Risk' (1 = At-Risk, 0 = Not At-Risk)
# Mock Rule for training: Student is At-Risk (1) if Academic < 65 AND Attendance < 75
df['predicted_at_risk'] = (
    (df['academic_performance'] < 65) & 
    (df['attendance_rate'] < 75)
).astype(int)

# --- 3. Train Logistic Regression Model ---
print("\nTraining Logistic Regression model...")

# Define features (X) and target (y)
X = df[['academic_performance', 'attendance_rate', 'avg_participation_rating']]
y = df['predicted_at_risk']

# Split data (80% train, 20% test)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Initialize and train the Logistic Regression model
log_reg_model = LogisticRegression(solver='liblinear', random_state=42)
log_reg_model.fit(X_train, y_train)

# --- 4. Save the Model ---
with open(MODEL_PATH, 'wb') as file:
    pickle.dump(log_reg_model, file)

print("---------------------------------------------------------")
print(f"✅ Logistic Regression Model trained and saved successfully.")
print(f"File location: {MODEL_PATH}")
print(f"Model Accuracy (on test set): {log_reg_model.score(X_test, y_test):.2f}")
print("---------------------------------------------------------")
print("NEXT STEP: Now update your app/ai_model.py with the code from Step 2.")