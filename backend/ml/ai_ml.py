import pandas as pd
import joblib
import sys
import json
import re
import random
import os
from collections import defaultdict 
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB, GaussianNB
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, IsolationForest
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
import numpy as np
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import classification_report, mean_squared_error, accuracy_score, confusion_matrix, r2_score, mean_absolute_error
from sklearn.cluster import KMeans
from sklearn.tree import DecisionTreeClassifier
try:
    from prophet import Prophet
except ImportError:
    print(json.dumps({"error": "Prophet library not found. Please run 'pip install prophet'"}))
    sys.exit(1)
import logging
try:
    import networkx as nx
except ImportError:
    print(json.dumps({"error": "NetworkX library not found. Please run 'pip install networkx'"}))
    sys.exit(1)

logging.getLogger('cmdstanpy').setLevel(logging.WARNING)

# ===============================================
# === MEDICAL REPORT ANALYZER ===
# ===============================================
def analyze_medical_report(text):
    if not isinstance(text, str) or not text.strip():
        return {
            "summary": "Report text missing.",
            "detected_conditions": [],
            "risk_score": 0,
            "risk_level": "Low",
            "primary_category": "General"
        }

    lowered = re.sub(r"\s+", " ", text.lower()).strip()
    sample = lowered[:2000]
    non_printable = sum(1 for ch in sample if ord(ch) < 9 or (ord(ch) < 32 and ch not in "\n\t\r"))
    if sample.startswith("%pdf-") or (non_printable / max(1, len(sample)) > 0.12):
        return {
            "summary": "Report text looks like raw PDF bytes. Please upload the document for OCR.",
            "detected_conditions": [],
            "risk_score": 0,
            "risk_level": "Low",
            "primary_category": "General",
            "error": "invalid_report_text"
        }

    patterns = [
        (r"\bliver cancer\b|\bhepatocellular carcinoma\b|\bhepatic carcinoma\b", "Liver Cancer", "Oncology", 12),
        (r"\bbreast cancer\b|\bmammary carcinoma\b", "Breast Cancer", "Oncology", 11),
        (r"\blung cancer\b|\bbronchogenic carcinoma\b", "Lung Cancer", "Oncology", 11),
        (r"\bcolon cancer\b|\bcolorectal cancer\b", "Colon Cancer", "Oncology", 11),
        (r"\bprostate cancer\b", "Prostate Cancer", "Oncology", 10),
        (r"\bmalignancy\b|\bcarcinoma\b|\btumor\b|\bcancer\b", "Malignancy", "Oncology", 9),
        (r"\bhepatitis\b|\bcirrhosis\b|\bfatty liver\b|\bliver disease\b", "Liver Disease", "Hepatic", 7),
        (r"\bkidney disease\b|\brenal failure\b|\bckd\b", "Kidney Disease", "Renal", 7),
        (r"\bheart failure\b|\bcardiac arrest\b|\bmyocardial infarction\b|\bheart attack\b", "Cardiac Event", "Cardiovascular", 10),
        (r"\bhypertension\b|\bhigh blood pressure\b", "Hypertension", "Cardiovascular", 6),
        (r"\bhypotension\b|\blow blood pressure\b", "Hypotension", "Cardiovascular", 5),
        (r"\bblood pressure\b|\bbp\b", "Blood Pressure Issue", "Cardiovascular", 4),
        (r"\barrhythmia\b|\birregular heartbeat\b", "Arrhythmia", "Cardiovascular", 7),
        (r"\bdiabetes\b|\btype 1 diabetes\b|\btype 2 diabetes\b", "Diabetes", "Metabolic", 6),
        (r"\bhyperglycemia\b|\bglucose\b|\bhigh blood sugar\b", "Elevated Glucose", "Metabolic", 4),
        (r"\basthma\b|\bcopd\b|\bchronic obstructive\b", "Respiratory Disease", "Respiratory", 6),
        (r"\bpneumonia\b|\brespiratory infection\b", "Pneumonia", "Respiratory", 7),
        (r"\bstroke\b|\bcerebrovascular\b", "Stroke", "Neurological", 9),
        (r"\bseizure\b|\bepilepsy\b", "Seizure", "Neurological", 6),
        (r"\banemia\b|\blow hemoglobin\b", "Anemia", "Blood", 4),
        (r"\bsepsis\b|\bsystemic infection\b", "Sepsis", "Infection", 9),
        (r"\binfection\b|\bfever\b|\bcovid\b", "Infection", "Infection", 5),
    ]

    detected = []
    total_score = 0
    categories = {}

    for pattern, label, category, score in patterns:
        if re.search(pattern, lowered):
            detected.append(label)
            total_score += score
            categories[category] = categories.get(category, 0) + 1

    risk = "Low"
    if total_score >= 20:
        risk = "Critical"
    elif total_score >= 12:
        risk = "High"
    elif total_score >= 6:
        risk = "Moderate"

    return {
        "summary": f"Detected: {', '.join(detected)}" if detected else "Normal report.",
        "detected_conditions": detected,
        "risk_score": min(total_score * 5, 100),
        "risk_level": risk,
        "primary_category": max(categories, key=categories.get) if categories else "General"
    }

# ===============================================
# === EMERGENCY ALERT CLASSIFIER ===
# ===============================================

def train_and_save_model(csv_path='911_calls.csv', model_output_path='emergency_classifier.joblib'):
    print(f"Starting model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        df = df.dropna(subset=['title'])
        def map_category(title):
            title_lower = title.lower()
            if 'fire:' in title_lower: return 'fire'
            if 'traffic:' in title_lower: return 'accident'
            if 'ems:' in title_lower:
                if any(keyword in title_lower for keyword in ['cardiac', 'chest pain', 'heart', 'cpr']): return 'cardiac_issue'
                if any(keyword in title_lower for keyword in ['accident', 'mva', 'vehicle']): return 'accident'
                return 'medical_emergency'
            return 'other'
        df['category'] = df['title'].apply(map_category)
        df_model = df[df['category'] != 'other'][['title', 'category']]
        if df_model.empty:
            print("Error: No data to train on after filtering.")
            return
        print(f"Data processed. Training on {len(df_model)} samples.")
        X = df_model['title']
        y = df_model['category']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(stop_words='english')),
            ('nb', MultinomialNB())
        ])
        print("Fitting pipeline...")
        pipeline.fit(X_train, y_train)
        
        y_pred = pipeline.predict(X_test)
        print("\n--- Model: Multinomial Naive Bayes (Alert Classifier) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")
        
        joblib.dump(pipeline, model_output_path)
        print(f"Model successfully saved to {model_output_path}")
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found.")
    except Exception as e:
        print(f"An error occurred during training: {e}")

def get_priority(category):
    if category in ['cardiac_issue', 'accident', 'fire']: return 'High'
    if category == 'medical_emergency': return 'Medium'
    return 'Low'

def predict_emergency(text_input, model_path='emergency_classifier.joblib'):
    try:
        model = joblib.load(model_path)
        predicted_category = model.predict([text_input])[0]
        priority = get_priority(predicted_category)
        return {
            "type": predicted_category,
            "priority": priority,
            "original_message": text_input
        }
    except FileNotFoundError:
        return {"error": "Model file (emergency_classifier.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during prediction: {e}"}

# ===============================================
# === DONOR COMPATIBILITY ===
# ===============================================

def train_compatibility_model(csv_path='compatibility_data.csv', model_output_path='compatibility_model.joblib'):
    print(f"Starting compatibility model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        df = df.dropna()
        if 'is_compatible' not in df.columns:
            print(f"Error: Target column 'is_compatible' not found in {csv_path}.")
            return
        X = df.drop('is_compatible', axis=1)
        y = df['is_compatible']
        categorical_features = ['receiver_blood_type', 'receiver_gender', 'donor_blood_type', 'donor_gender', 'organ_type']
        numerical_features = ['receiver_age', 'donor_age', 'location_distance']
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        clf = Pipeline(steps=[('preprocessor', preprocessor),
                            ('classifier', LogisticRegression(random_state=42, class_weight='balanced'))])
            
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        print("Fitting compatibility pipeline...")
        clf.fit(X_train, y_train)
        
        y_pred = clf.predict(X_test)
        target_names = ['Not Compatible (0)', 'Compatible (1)']
        print("\n--- Model: Logistic Regression (Donor Compatibility) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred, target_names=target_names))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")

        joblib.dump(clf, model_output_path)
        print(f"Model successfully saved to {model_output_path}")
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during compatibility training: {e}")

def predict_compatibility(input_data_dict, model_path='compatibility_model.joblib'):
    try:
        model = joblib.load(model_path)
        input_df = pd.DataFrame([input_data_dict])
        probability = model.predict_proba(input_df)[0][1]
        return {
            "probability": round(probability, 4)
        }
    except FileNotFoundError:
        return {"error": "Model file (compatibility_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during compatibility prediction: {e}"}

# ===============================================
# === HOSPITAL RECOMMENDATION ===
# ===============================================

def train_recommendation_model(csv_path='hospital_data.csv', model_output_path='hospital_recommendation_model.joblib'):
    print(f"Starting recommendation model training with data from {csv_path}...")
    
    try:
        df = pd.read_csv(csv_path)
        df = df.dropna()
        
        if 'is_best_choice' not in df.columns:
            print(f"Error: Target column 'is_best_choice' not found in {csv_path}.")
            return

        X = df.drop('is_best_choice', axis=1)
        y = df['is_best_choice']
        
        categorical_features = ['emergency_type']
        numerical_features = ['distance_km', 'traffic_level', 'hospital_rating']
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        clf = Pipeline(steps=[('preprocessor', preprocessor),
                            ('classifier', RandomForestClassifier(random_state=42))])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting recommendation pipeline...")
        clf.fit(X_train, y_train)
        
        y_pred = clf.predict(X_test)
        target_names = ['Not Best (0)', 'Best Choice (1)']
        print("\n--- Model: RandomForestClassifier (Hospital Recommendation) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred, target_names=target_names))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")
        
        joblib.dump(clf, model_output_path)
        print(f"Model successfully saved to {model_output_path}")
        
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during recommendation training: {e}")

def predict_hospital_recommendation(input_data_json, model_path='hospital_recommendation_model.joblib'):
    try:
        model = joblib.load(model_path)

        input_data = input_data_json
        if isinstance(input_data_json, str):
            if os.path.isfile(input_data_json):
                with open(input_data_json, "r", encoding="utf-8") as handle:
                    input_data = json.load(handle)
            else:
                input_data = json.loads(input_data_json)
        if not isinstance(input_data, list) or len(input_data) == 0:
            return {"error": "Input must be a non-empty list of hospitals."}

        input_df = pd.DataFrame(input_data)
        probabilities = model.predict_proba(input_df)
        scores = probabilities[:, 1]

        ranked = []
        for idx, score in enumerate(scores):
            payload = dict(input_data[idx])
            payload["ml_score"] = round(float(score), 4)
            payload["index"] = idx
            ranked.append(payload)

        ranked.sort(key=lambda item: item.get("ml_score", 0), reverse=True)
        best_hospital = ranked[0] if ranked else None

        return {
            "best": best_hospital,
            "ranked": ranked,
        }

    except FileNotFoundError:
        return {"error": "Model file (hospital_recommendation_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during recommendation prediction: {e}"}

# ===============================================
# === HEALTH RISK PREDICTION ===
# ===============================================

def train_health_risk_model(csv_path='health_risk_data.csv', model_output_path='health_risk_model.joblib'):
    print(f"Starting health risk model training with data from {csv_path}...")

    try:
        df = pd.read_csv(csv_path)
        processed_df = pd.DataFrame()
        processed_df['age'] = df['Age']
        processed_df['bmi'] = df['BMI']
        processed_df['heart_rate'] = df['Heart Rate']
        processed_df['has_condition'] = df['Diabetes']
        processed_df['lifestyle_factor'] = df['Diet']
        processed_df['risk_level'] = df['Heart Attack Risk']

        try:
            processed_df['blood_pressure'] = df['Blood Pressure'].apply(lambda x: int(x.split('/')[0]))
        except Exception as e:
            print(f"Warning: Could not parse 'Blood Pressure' column. Error: {e}. Skipping this feature.")

        numerical_features = ['age', 'bmi', 'blood_pressure', 'heart_rate', 'has_condition']
        categorical_features = ['lifestyle_factor']

        if 'blood_pressure' not in processed_df.columns:
            numerical_features.remove('blood_pressure')

        all_features = numerical_features + categorical_features
        processed_df = processed_df.dropna(subset=all_features + ['risk_level'])

        if 'risk_level' not in processed_df.columns:
            print("Error: Target column 'Heart Attack Risk' (renamed to 'risk_level') not found or is empty after processing.")
            return

        if processed_df.empty:
            print("Error: No data remaining after processing and cleaning. Check your CSV.")
            return

        X = processed_df[all_features]
        y = processed_df['risk_level']

        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])

        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])

        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])

        clf = Pipeline(steps=[('preprocessor', preprocessor),
                    ('classifier', LogisticRegression(random_state=42, class_weight='balanced'))])

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        print("Fitting health risk pipeline...")
        clf.fit(X_train, y_train)

        y_pred = clf.predict(X_test)
        target_names = ['Low Risk (0)', 'High Risk (1)']
        print("\n--- Model: Logistic Regression (Health Risk) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred, target_names=target_names))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")

        joblib.dump(clf, model_output_path)
        print(f"Model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print("Error: The file health_risk_data.csv was not found. Please download it and name it 'health_risk_data.csv'.")
    except KeyError as e:
        print(f"Error: A required column is missing from your CSV file: {e}. Please check the file.")
    except Exception as e:
        print(f"An error occurred during health risk training: {e}")

def predict_health_risk(input_data_dict, model_path='health_risk_model.joblib'):
    try:
        model = joblib.load(model_path)
        input_df = pd.DataFrame([input_data_dict])
        prediction = model.predict(input_df)[0]
        proba = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(input_df)[0][1]
        risk_map = {0: 'Low', 1: 'High'}
        risk_level = risk_map.get(prediction, 'Unknown')
        risk_score = int(round((proba or (0.8 if risk_level == 'High' else 0.3)) * 100))
        return {
            "risk_level": risk_level,
            "risk_value": int(prediction),
            "risk_score": risk_score,
        }
    except FileNotFoundError:
        return {"error": "Model file (health_risk_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during health risk prediction: {e}. Check input features."}

# ===============================================
# === USER ACTIVITY CLUSTERING ===
# ===============================================

def train_activity_cluster_model(csv_path='user_activity_data.csv', model_output_path='activity_cluster_model.joblib'):
    print(f"Starting activity cluster model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        features = ['sos_usage', 'donations_made', 'health_logs']
        if not all(col in df.columns for col in features):
            print(f"Error: CSV must contain all of these columns: {features}")
            return
        df_features = df[features].dropna()
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('kmeans', KMeans(n_clusters=3, random_state=42, n_init=10))
        ])
        print("Fitting K-Means clustering pipeline...")
        pipeline.fit(df_features)
        
        print("\n--- Model: K-Means (Activity Cluster) ---")
        inertia = pipeline.named_steps['kmeans'].inertia_
        centers = pipeline.named_steps['kmeans'].cluster_centers_
        print(f"Inertia (Sum of squared distances): {inertia:.4f}")
        print(f"Cluster Centers (Scaled):\n{centers}")
        print("-" * 50 + "\n")
        
        joblib.dump(pipeline, model_output_path)
        print(f"Activity cluster model successfully saved to {model_output_path}")
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during cluster training: {e}")

def predict_activity_cluster(input_data_dict, model_path='activity_cluster_model.joblib'):
    try:
        model = joblib.load(model_path)
        cluster_map = {0: "Inactive", 1: "Active", 2: "Moderate"}
        input_df = pd.DataFrame([input_data_dict])
        features = ['sos_usage', 'donations_made', 'health_logs']
        input_df = input_df[features]
        prediction = model.predict(input_df)[0]
        cluster_label = cluster_map.get(prediction, "Unknown")
        return {
            "cluster_label": cluster_label,
            "cluster_id": int(prediction)
        }
    except FileNotFoundError:
        return {"error": "Model file (activity_cluster_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during cluster prediction: {e}"}

# ===============================================
# === BEHAVIOR FORECAST ===
# ===============================================

def train_behavior_forecast_model(csv_path='user_forecast_data.csv', model_output_path='behavior_forecast_model.joblib'):
    print(f"Starting behavior forecast model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        features = ['past_donations']
        target = 'future_donations'
        if not all(col in df.columns for col in features + [target]):
            print(f"Error: CSV must contain all of these columns: {features + [target]}")
            return
        df_model = df.dropna(subset=features + [target])
        X = df_model[features]
        y = df_model[target]
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = LinearRegression()
        print("Fitting Linear Regression forecast model...")
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_test)
        print("\n--- Model: Linear Regression (Behavior Forecast) ---")
        print(f"R-squared (R2): {r2_score(y_test, y_pred):.4f}")
        print(f"Mean Absolute Error (MAE): {mean_absolute_error(y_test, y_pred):.4f}")
        print(f"Root Mean Squared Error (RMSE): {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(model, model_output_path)
        print(f"Behavior forecast model successfully saved to {model_output_path}")
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during forecast training: {e}")

def predict_behavior_forecast(input_data_dict, model_path='behavior_forecast_model.joblib'):
    try:
        model = joblib.load(model_path)
        input_df = pd.DataFrame([input_data_dict])
        features = ['past_donations']
        input_df = input_df[features]
        prediction = model.predict(input_df)[0]
        predicted_value = max(0, round(prediction))
        return {
            "forecasted_donations_next_period": int(predicted_value)
        }
    except FileNotFoundError:
        return {"error": "Model file (behavior_forecast_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during forecast prediction: {e}"}

# ===============================================
# === EMERGENCY HOTSPOT CLUSTERING ===
# ===============================================

def train_emergency_hotspot_model(csv_path='emergency_hotspot_data.csv', model_output_path='emergency_hotspot_model.joblib'):
    print(f"Starting emergency hotspot model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour_of_day'] = df['timestamp'].dt.hour
        except Exception as e:
            print(f"Warning: Could not parse 'timestamp'. Using random hour. Error: {e}")
            df['hour_of_day'] = np.random.randint(0, 24, df.shape[0])
            
        df = df.dropna(subset=['lat', 'lng', 'emergency_type', 'severity', 'hour_of_day'])

        numerical_features = ['lat', 'lng', 'hour_of_day']
        categorical_features = ['emergency_type', 'severity']
        
        if df.empty:
            print("Error: No data to train on after processing.")
            return

        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('kmeans', KMeans(n_clusters=3, random_state=42, n_init=10))
        ])
        
        print("Fitting K-Means hotspot pipeline...")
        pipeline.fit(df)
        
        print("\n--- Model: K-Means (Hotspot Cluster) ---")
        inertia = pipeline.named_steps['kmeans'].inertia_
        centers = pipeline.named_steps['kmeans'].cluster_centers_
        print(f"Inertia (Sum of squared distances): {inertia:.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(pipeline, model_output_path)
        print(f"Emergency hotspot model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during hotspot training: {e}")

def predict_emergency_hotspots(input_data_json, model_path='emergency_hotspot_model.joblib'):
    try:
        model = joblib.load(model_path)
        input_data = input_data_json
        if isinstance(input_data_json, str):
            if os.path.isfile(input_data_json):
                with open(input_data_json, "r", encoding="utf-8") as handle:
                    input_data = json.load(handle)
            else:
                input_data = json.loads(input_data_json)
        
        if not isinstance(input_data, list) or len(input_data) == 0:
            return {"error": "Input must be a non-empty list of emergencies."}

        df = pd.DataFrame(input_data)
        
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour_of_day'] = df['timestamp'].dt.hour
        except Exception as e:
            df['hour_of_day'] = np.random.randint(0, 24, df.shape[0])

        predictions = model.predict(df)
        
        cluster_map = {0: "High-Density Zone", 1: "Medium-Density Zone", 2: "Low-Density Zone"}
        
        df['cluster_label'] = [cluster_map.get(p, "Unknown") for p in predictions]
        df['cluster_id'] = predictions

        if 'timestamp' in df.columns:
            df['timestamp'] = df['timestamp'].astype(str)

        return df.to_dict('records')
        
    except FileNotFoundError:
        return {"error": "Model file (emergency_hotspot_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during hotspot prediction: {e}"}

# ===============================================
# === DISEASE OUTBREAK FORECAST ===
# ===============================================
def train_outbreak_forecast_model(csv_path='outbreak_data.csv', model_output_path='outbreak_forecast_models.joblib'):
    print(f"Starting outbreak forecast model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        required_cols = ['date', 'disease_name', 'region', 'cases']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df['date'] = pd.to_datetime(df['date'])
        df = df.rename(columns={'date': 'ds', 'cases': 'y'})
        
        models = {}
        
        for (disease, region), group_df in df.groupby(['disease_name', 'region']):
            if len(group_df) < 2: 
                print(f"Skipping {disease} in {region}: not enough data points.")
                continue
                
            print(f"Training model for: {disease} in {region}...")
            
            m = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False)
            m.fit(group_df[['ds', 'y']])
            
            models[(disease, region)] = m
            
        if not models:
            print("No models were trained. Check your data.")
            return
        
        print("\n--- Model: Prophet (Time-Series) ---")
        print(f"Successfully trained and saved {len(models)} model(s).")
        print("Models trained for combinations:")
        for key in models.keys():
            print(f"- {key[0]} in {key[1]}")
        print("-" * 50 + "\n")

        joblib.dump(models, model_output_path)
        print(f"Outbreak forecast models dictionary successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during outbreak forecast training: {e}")

def predict_outbreak_forecast(input_data_dict, model_path='outbreak_forecast_models.joblib'):
    try:
        models = joblib.load(model_path)
        
        disease = input_data_dict.get('disease_name')
        region = input_data_dict.get('region')
        days = int(input_data_dict.get('days_to_predict', 30))
        
        key = (disease, region)
        
        if key not in models:
            return {"error": f"No forecast model found for {disease} in {region}. Please train the model."}
            
        m = models[key]
        future = m.make_future_dataframe(periods=days)
        forecast = m.predict(future)
        
        results = []
        forecast_data = forecast.tail(days)
        
        for index, row in forecast_data.iterrows():
            results.append({
                "date": row['ds'].strftime('%Y-%m-%d'),
                "predicted_cases": round(max(0, row['yhat'])),
                "confidence_low": round(max(0, row['yhat_lower'])),
                "confidence_high": round(max(0, row['yhat_upper']))
            })
            
        return {
            "disease_name": disease,
            "region": region,
            "forecast": results
        }
        
    except FileNotFoundError:
        return {"error": "Model file (outbreak_forecast_models.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during outbreak forecast prediction: {e}"}

# ===============================================
# === EMERGENCY SEVERITY PREDICTION ===
# ===============================================

def train_severity_model(csv_path='emergency_severity_data.csv', model_output_path='emergency_severity_model.joblib'):
    print(f"Starting emergency severity model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'severity'
        numerical_features = ['population_density', 'avg_response_time_min']
        categorical_features = ['emergency_type', 'region']
        
        required_cols = numerical_features + categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        clf = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', RandomForestClassifier(random_state=42, class_weight='balanced'))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting severity prediction pipeline...")
        clf.fit(X_train, y_train)
        
        y_pred = clf.predict(X_test)
        print("\n--- Model: RandomForestClassifier (Severity) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")
        
        joblib.dump(clf, model_output_path)
        print(f"Emergency severity model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during severity model training: {e}")

def predict_severity(input_data_dict, model_path='emergency_severity_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        
        prediction = model.predict(input_df)[0]
        
        return {
            "predicted_severity": str(prediction)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (emergency_severity_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during severity prediction: {e}"}

# ===============================================
# === DONOR/ORGAN AVAILABILITY ===
# ===============================================

def train_availability_model(csv_path='donor_availability_data.csv', model_output_path='donor_availability_model.joblib'):
    print(f"Starting donor availability model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'future_availability_score'
        numerical_features = ['month', 'donation_frequency', 'hospital_stock_level']
        categorical_features = ['region', 'resource_type']
        
        required_cols = numerical_features + categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        reg = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('regressor', RandomForestRegressor(random_state=42, n_estimators=100))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting availability prediction pipeline...")
        reg.fit(X_train, y_train)
        
        y_pred = reg.predict(X_test)
        print("\n--- Model: RandomForestRegressor (Availability) ---")
        print(f"R-squared (R2): {r2_score(y_test, y_pred):.4f}")
        print(f"Mean Absolute Error (MAE): {mean_absolute_error(y_test, y_pred):.4f}")
        print(f"Root Mean Squared Error (RMSE): {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(reg, model_output_path)
        print(f"Donor availability model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during availability model training: {e}")

def predict_availability(input_data_dict, model_path='donor_availability_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        
        prediction = model.predict(input_df)[0]
        
        predicted_score = max(0, min(100, round(prediction, 2)))
        
        return {
            "predicted_availability_score": predicted_score
        }
        
    except FileNotFoundError:
        return {"error": "Model file (donor_availability_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during availability prediction: {e}"}

# ===============================================
# === RESOURCE ALLOCATION ===
# ===============================================

def _get_discretized_state(emergency_count, capacity_percent):
    if emergency_count <= 3:
        emerg_level = "Low"
    elif emergency_count <= 7:
        emerg_level = "Medium"
    else:
        emerg_level = "High"
        
    if capacity_percent <= 30:
        cap_level = "Low"
    elif capacity_percent <= 70:
        cap_level = "Medium"
    else:
        cap_level = "High"
        
    return (emerg_level, cap_level)

def _get_reward(state, action):
    emerg_level, cap_level = state
    
    if emerg_level == "Low":
        if action == 0: return 20
        if action == 1: return -10
        if action == 2: return -20
    elif emerg_level == "Medium":
        if action == 0: return -30
        if action == 1: return 20
        if action == 2: return -10
    elif emerg_level == "High":
        if action == 0: return -50
        if action == 1: return -30
        if action == 2: return 20
    
    return -1

def train_allocation_model(model_output_path='allocation_q_table.joblib'):
    print("Starting resource allocation model training (Q-Learning)...")
    
    states_emerg = ["Low", "Medium", "High"]
    states_cap = ["Low", "Medium", "High"]
    actions = [0, 1, 2]
    
    q_table = defaultdict(lambda: np.zeros(len(actions)))
    
    alpha = 0.1
    gamma = 0.9
    epsilon = 0.1
    n_episodes = 10000
    
    print(f"Running {n_episodes} training simulations...")

    for i in range(n_episodes):
        emerg_count = random.randint(0, 10)
        cap_percent = random.randint(0, 100)
        state = _get_discretized_state(emerg_count, cap_percent)
        
        if random.uniform(0, 1) < epsilon:
            action = random.choice(actions)
        else:
            action = np.argmax(q_table[state])
            
        reward = _get_reward(state, action)
        
        next_emerg_count = random.randint(0, 10)
        next_cap_percent = random.randint(0, 100)
        next_state = _get_discretized_state(next_emerg_count, next_cap_percent)
        
        old_value = q_table[state][action]
        next_max = np.max(q_table[next_state])
        
        new_value = (1 - alpha) * old_value + alpha * (reward + gamma * next_max)
        q_table[state][action] = new_value

    print("Q-Learning training complete.")
    
    print("\n--- Model: Q-Learning (Allocation) ---")
    print(f"Trained Q-Table with {len(q_table)} states.")
    print("Sample of Learned Q-Table (State: [Action 0, Action 1, Action 2]):")
    for i, (state, actions) in enumerate(q_table.items()):
        if i >= 5: 
            break
        print(f"  {state}: {actions}")
    print("-" * 50 + "\n")
    
    joblib.dump(dict(q_table), model_output_path)
    print(f"Allocation Q-Table successfully saved to {model_output_path}")

def predict_allocation(input_data_dict, model_path='allocation_q_table.joblib'):
    try:
        q_table = joblib.load(model_path)
        
        emerg_count = int(input_data_dict.get('emergency_count'))
        cap_percent = int(input_data_dict.get('hospital_capacity_percent'))
        
        state = _get_discretized_state(emerg_count, cap_percent)
        
        if state not in q_table:
            action_id = 0
        else:
            action_id = np.argmax(q_table[state])
            
        action_map = {0: "Send 1 Ambulance", 1: "Send 2 Ambulances", 2: "Send 3 Ambulances"}
        
        return {
            "optimal_action": action_map.get(action_id, "Unknown Action"),
            "action_id": int(action_id)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (allocation_q_table.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during allocation prediction: {e}"}

# ===============================================
# === POLICY & PERFORMANCE ===
# ===============================================

def train_policy_segmentation_model(csv_path='policy_data.csv', model_output_path='policy_segmentation_model.joblib'):
    print(f"Starting policy segmentation model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        features = ['emergency_rate', 'avg_response_time', 'hospital_bed_occupancy']
        if not all(col in df.columns for col in features):
            print(f"Error: CSV must contain all of these columns: {features}")
            return
            
        df_features = df[features].dropna()
        if df_features.empty:
            print("Error: No data to train on after cleaning.")
            return

        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('kmeans', KMeans(n_clusters=3, random_state=42, n_init=10))
        ])
        
        print("Fitting K-Means policy segmentation pipeline...")
        pipeline.fit(df_features)
        
        print("\n--- Model: K-Means (Policy Segmentation) ---")
        inertia = pipeline.named_steps['kmeans'].inertia_
        centers = pipeline.named_steps['kmeans'].cluster_centers_
        print(f"Inertia (Sum of squared distances): {inertia:.4f}")
        print(f"Cluster Centers (Scaled):\n{centers}")
        print("-" * 50 + "\n")
        
        joblib.dump(pipeline, model_output_path)
        print(f"Policy segmentation model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during segmentation training: {e}")

def predict_policy_segmentation(input_data_dict, model_path='policy_segmentation_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        cluster_map = {0: "Well-Served Region", 1: "Critical-Priority Region", 2: "Stressed Region"}
        
        input_df = pd.DataFrame([input_data_dict])
        features = ['emergency_rate', 'avg_response_time', 'hospital_bed_occupancy']
        input_df = input_df[features]
        
        prediction = model.predict(input_df)[0]
        cluster_label = cluster_map.get(prediction, "Unknown Segment")
        
        return {
            "segment_label": cluster_label,
            "cluster_id": int(prediction)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (policy_segmentation_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during segmentation prediction: {e}"}

def train_healthcare_performance_model(csv_path='policy_data.csv', model_output_path='healthcare_performance_model.joblib'):
    print(f"Starting healthcare performance score model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'health_outcome_score'
        features = ['emergency_rate', 'avg_response_time', 'hospital_bed_occupancy']
        
        required_cols = features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df[features]
        y = df[target]
        
        pipeline = Pipeline(steps=[
            ('scaler', StandardScaler()),
            ('regressor', LinearRegression())
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting performance score pipeline...")
        pipeline.fit(X_train, y_train)
        
        y_pred = pipeline.predict(X_test)
        print("\n--- Model: Linear Regression (Performance Score) ---")
        print(f"R-squared (R2): {r2_score(y_test, y_pred):.4f}")
        print(f"Mean Absolute Error (MAE): {mean_absolute_error(y_test, y_pred):.4f}")
        print(f"Root Mean Squared Error (RMSE): {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(pipeline, model_output_path)
        print(f"Healthcare performance model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during performance model training: {e}")

def predict_healthcare_performance(input_data_dict, model_path='healthcare_performance_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        features = ['emergency_rate', 'avg_response_time', 'hospital_bed_occupancy']
        input_df = input_df[features]
        
        prediction = model.predict(input_df)[0]
        
        score = max(0, min(100, round(prediction, 1)))
        
        return {
            "predicted_performance_score": score
        }
        
    except FileNotFoundError:
        return {"error": "Model file (healthcare_performance_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during performance score prediction: {e}"}


# ===============================================
# === ANOMALY DETECTION ===
# ===============================================

def train_anomaly_detection_model(csv_path='anomaly_data.csv', model_output_path='anomaly_detection_model.joblib'):
    print(f"Starting anomaly detection model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        numerical_features = ['daily_emergency_count', 'hospital_admissions', 'disease_reports']
        categorical_features = ['region']
        
        required_cols = numerical_features + categorical_features
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df[required_cols]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('anomaly_detector', IsolationForest(contamination='auto', random_state=42))
        ])
        
        print("Fitting anomaly detection pipeline...")
        pipeline.fit(X)
        
        print("\n--- Model: Isolation Forest (Anomaly Detection) ---")
        y_pred = pipeline.predict(X)
        anomalies = (y_pred == -1).sum()
        print(f"Total data points: {len(X)}")
        print(f"Detected anomalies in training data: {anomalies}")
        print("-" * 50 + "\n")
        
        joblib.dump(pipeline, model_output_path)
        print(f"Anomaly detection model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during anomaly model training: {e}")

def predict_anomaly(input_data_dict, model_path='anomaly_detection_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        
        prediction = model.predict(input_df)[0]
        
        is_anomaly = prediction == -1
        
        return {
            "is_anomaly": bool(is_anomaly),
            "message": "Unusual pattern detected!" if is_anomaly else "Data pattern appears normal."
        }
        
    except FileNotFoundError:
        return {"error": "Model file (anomaly_detection_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during anomaly prediction: {e}"}

# ===============================================
# === HOSPITAL SEVERITY PREDICTION ===
# ===============================================

def train_hospital_severity_model(csv_path='hospital_severity_data.csv', model_output_path='hospital_severity_model.joblib'):
    print(f"Starting hospital severity model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'severity'
        numerical_features = ['age', 'heart_rate', 'blood_pressure_systolic', 'distance_km']
        categorical_features = ['emergency_type']
        
        required_cols = numerical_features + categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        clf = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', RandomForestClassifier(random_state=42, class_weight='balanced'))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting hospital severity prediction pipeline...")
        clf.fit(X_train, y_train)
        
        y_pred = clf.predict(X_test)
        print("\n--- Model: RandomForestClassifier (Hospital Severity) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")
        
        joblib.dump(clf, model_output_path)
        print(f"Hospital severity model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during hospital severity model training: {e}")

def predict_hospital_severity(input_data_dict, model_path='hospital_severity_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        
        prediction = model.predict(input_df)[0]
        
        return {
            "predicted_severity": str(prediction)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (hospital_severity_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during hospital severity prediction: {e}"}

# ===============================================
# === AMBULANCE ETA & ROUTE ===
# ===============================================

def _get_city_graph():
    G = nx.Graph()
    edges = [
        ('Central City General', 'St. Jude Hospital', 8),
        ('Central City General', 'Mercy West', 12),
        ('Central City General', 'Downtown', 5),
        ('St. Jude Hospital', 'Downtown', 6),
        ('St. Jude Hospital', 'North Sector', 10),
        ('Mercy West', 'Downtown', 7),
        ('Mercy West', 'West Suburbs', 15),
        ('Downtown', 'North Sector', 9),
        ('Downtown', 'South Suburbs', 10),
        ('North Sector', 'North Suburbs', 14),
        ('South Suburbs', 'West Suburbs', 16),
    ]
    G.add_weighted_edges_from(edges)
    return G

def train_eta_model(csv_path='eta_data.csv', model_output_path='eta_model.joblib'):
    print(f"Starting ETA model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)

        target = 'eta_minutes'
        numerical_features = ['distance_km', 'precipitation_mm', 'wind_kph', 'hour']

        if not all(col in df.columns for col in numerical_features + [target]):
            synthetic = []
            for _ in range(1200):
                distance_km = max(1, np.random.gamma(2.0, 5.0))
                precipitation = max(0.0, np.random.exponential(2.0))
                wind = max(5.0, np.random.normal(18.0, 6.0))
                hour = np.random.randint(0, 24)
                base_speed = 40 - min(12, precipitation * 1.5) - min(8, (wind - 15) * 0.2)
                base_speed = max(18, base_speed)
                eta_minutes = (distance_km / base_speed) * 60
                eta_minutes *= 1.0 + (0.15 if hour in {7, 8, 9, 17, 18, 19} else 0)
                synthetic.append({
                    "distance_km": round(distance_km, 2),
                    "precipitation_mm": round(precipitation, 2),
                    "wind_kph": round(wind, 2),
                    "hour": int(hour),
                    "eta_minutes": round(eta_minutes, 2),
                })
            df = pd.DataFrame(synthetic)

        df = df.dropna(subset=numerical_features + [target])
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df[numerical_features]
        y = df[target]

        reg = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('regressor', RandomForestRegressor(random_state=42, n_estimators=160))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting ETA prediction pipeline...")
        reg.fit(X_train, y_train)
        
        y_pred = reg.predict(X_test)
        print("\n--- Model: RandomForestRegressor (ETA) ---")
        print(f"R-squared (R2): {r2_score(y_test, y_pred):.4f}")
        print(f"Mean Absolute Error (MAE): {mean_absolute_error(y_test, y_pred):.4f}")
        print(f"Root Mean Squared Error (RMSE): {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(reg, model_output_path)
        print(f"ETA model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during ETA model training: {e}")

def predict_eta_route(input_data_dict, model_path='eta_model.joblib'):
    try:
        model = joblib.load(model_path)
        distance_km = input_data_dict.get('distance_km')
        if distance_km is not None:
            ml_input = pd.DataFrame([
                {
                    'distance_km': float(distance_km),
                    'precipitation_mm': float(input_data_dict.get('precipitation_mm') or 0),
                    'wind_kph': float(input_data_dict.get('wind_kph') or 0),
                    'hour': int(input_data_dict.get('hour', 12)),
                }
            ])
            try:
                eta_minutes = float(model.predict(ml_input)[0])
            except Exception:
                base_speed = max(18, 40 - (ml_input['precipitation_mm'][0] * 1.5) - (ml_input['wind_kph'][0] * 0.2))
                eta_minutes = (float(distance_km) / base_speed) * 60
            return {
                "eta_minutes": round(eta_minutes, 2),
            }

        G = _get_city_graph()
        start_node = input_data_dict.get('start_node')
        end_node = input_data_dict.get('end_node')
        hour = int(input_data_dict.get('hour', 12))

        if start_node not in G or end_node not in G:
            return {"error": f"Invalid node. Must be one of: {list(G.nodes())}"}

        path = nx.dijkstra_path(G, source=start_node, target=end_node, weight='weight')
        base_time = nx.dijkstra_path_length(G, source=start_node, target=end_node, weight='weight')

        ml_input = pd.DataFrame([{ 'distance_km': base_time, 'precipitation_mm': 0, 'wind_kph': 0, 'hour': hour }])
        try:
            eta_minutes = float(model.predict(ml_input)[0])
        except Exception:
            eta_minutes = base_time

        return {
            "route": path,
            "base_minutes": round(base_time, 2),
            "eta_minutes": round(eta_minutes, 2)
        }

    except FileNotFoundError:
        return {"error": "Model file (eta_model.joblib) not found. Please train the model first."}
    except nx.NetworkXNoPath:
        return {"error": f"No path found between {start_node} and {end_node}."}
    except Exception as e:
        return {"error": f"An error occurred during ETA prediction: {e}"}

# ===============================================
# === HOSPITAL BED FORECAST ===
# ===============================================

def train_bed_forecast_model(csv_path='hospital_resource_data.csv', model_output_path='bed_forecast_model.joblib'):
    print(f"Starting bed forecast model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'next_week_bed_demand'
        numerical_features = ['emergency_count', 'disease_case_count', 'current_bed_occupancy']
        categorical_features = ['hospital_id']
        
        required_cols = numerical_features + categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value=0)), 
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        reg = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('regressor', LinearRegression())
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting bed forecast pipeline...")
        reg.fit(X_train, y_train)
        
        y_pred = reg.predict(X_test)
        print("\n--- Model: Linear Regression (Bed Forecast) ---")
        print(f"R-squared (R2): {r2_score(y_test, y_pred):.4f}")
        print(f"Mean Absolute Error (MAE): {mean_absolute_error(y_test, y_pred):.4f}")
        print(f"Root Mean Squared Error (RMSE): {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(reg, model_output_path)
        print(f"Bed forecast model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during bed forecast model training: {e}")

def predict_bed_forecast(input_data_dict, model_path='bed_forecast_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        
        prediction = model.predict(input_df)[0]
        
        predicted_demand = max(0, round(prediction))
        
        return {
            "predicted_bed_demand": int(predicted_demand)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (bed_forecast_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during bed forecast prediction: {e}"}

# ===============================================
# === STAFF ALLOCATION ===
# ===============================================

def train_staff_allocation_model(csv_path='staff_allocation_data.csv', model_output_path='staff_allocation_model.joblib'):
    print(f"Starting staff allocation model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'allocation_decision'
        categorical_features = ['patient_load', 'department', 'shift']
        
        required_cols = categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('cat', categorical_transformer, categorical_features)
            ])
        
        clf = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', DecisionTreeClassifier(random_state=42, class_weight='balanced'))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting staff allocation pipeline...")
        clf.fit(X_train, y_train)
        
        y_pred = clf.predict(X_test)
        print("\n--- Model: DecisionTreeClassifier (Staff Allocation) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")
        
        joblib.dump(clf, model_output_path)
        print(f"Staff allocation model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during staff allocation model training: {e}")

def predict_staff_allocation(input_data_dict, model_path='staff_allocation_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        
        prediction = model.predict(input_df)[0]
        
        return {
            "allocation_decision": str(prediction)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (staff_allocation_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during staff allocation prediction: {e}"}

# ===============================================
# === HOSPITAL PERFORMANCE ===
# ===============================================

def train_hospital_performance_model(csv_path='hospital_performance_data.csv', model_output_path='hospital_performance_model.joblib'):
    print(f"Starting hospital performance model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        features = ['avg_response_time', 'treatment_success_rate', 'patient_satisfaction', 'resource_utilization']
        
        required_cols = features + ['hospital_id']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df_features = df.dropna(subset=features)
        if df_features.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df_features[features]
        
        pipeline = Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler()),
            ('kmeans', KMeans(n_clusters=3, random_state=42, n_init=10))
        ])
        
        print("Fitting K-Means hospital performance pipeline...")
        pipeline.fit(X)
        
        print("\n--- Model: K-Means (Hospital Performance) ---")
        inertia = pipeline.named_steps['kmeans'].inertia_
        centers = pipeline.named_steps['kmeans'].cluster_centers_
        print(f"Inertia (Sum of squared distances): {inertia:.4f}")
        print(f"Cluster Centers (Scaled):\n{centers}")
        print("Note: Review centers to map clusters. e.g., low response_time + high success_rate = 'High-performing'")
        print("-" * 50 + "\n")
        
        joblib.dump(pipeline, model_output_path)
        print(f"Hospital performance model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during hospital performance model training: {e}")

def predict_hospital_performance(input_data_dict, model_path='hospital_performance_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        cluster_map = {0: "Needs Improvement", 1: "High-performing", 2: "Average"}
        
        input_df = pd.DataFrame([input_data_dict])
        features = ['avg_response_time', 'treatment_success_rate', 'patient_satisfaction', 'resource_utilization']
        input_df = input_df[features]
        
        prediction = model.predict(input_df)[0]
        cluster_label = cluster_map.get(int(prediction), "Unknown Segment")
        
        return {
            "performance_cluster": cluster_label,
            "cluster_id": int(prediction)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (hospital_performance_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during performance prediction: {e}"}

# ===============================================
# === PATIENT OUTCOME PREDICTION ===
# ===============================================

def train_recovery_model(csv_path='patient_outcome_data.csv', model_output_path='recovery_model.joblib'):
    print(f"Starting recovery probability model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'recovered'
        numerical_features = ['age', 'bmi', 'heart_rate', 'blood_pressure']
        categorical_features = ['diagnosis', 'treatment_type']
        
        required_cols = numerical_features + categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        clf = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', LogisticRegression(random_state=42, class_weight='balanced'))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting recovery probability pipeline...")
        clf.fit(X_train, y_train)
        
        y_pred = clf.predict(X_test)
        print("\n--- Model: Logistic Regression (Recovery Probability) ---")
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print("Classification Report:\n", classification_report(y_test, y_pred))
        print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
        print("-" * 50 + "\n")
        
        joblib.dump(clf, model_output_path)
        print(f"Recovery probability model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during recovery model training: {e}")

def predict_recovery(input_data_dict, model_path='recovery_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        input_df = pd.DataFrame([input_data_dict])
        
        prediction = model.predict_proba(input_df)[0][1]
        
        return {
            "recovery_probability": round(prediction, 4)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (recovery_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during recovery prediction: {e}"}

def train_stay_duration_model(csv_path='patient_outcome_data.csv', model_output_path='stay_duration_model.joblib'):
    print(f"Starting stay duration model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'stay_duration_days'
        numerical_features = ['age', 'bmi', 'heart_rate', 'blood_pressure']
        categorical_features = ['diagnosis', 'treatment_type']
        
        required_cols = numerical_features + categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        reg = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('regressor', RandomForestRegressor(random_state=42, n_estimators=100))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting stay duration pipeline...")
        reg.fit(X_train, y_train)
        
        y_pred = reg.predict(X_test)
        print("\n--- Model: RandomForestRegressor (Stay Duration) ---")
        print(f"R-squared (R2): {r2_score(y_test, y_pred):.4f}")
        print(f"Mean Absolute Error (MAE): {mean_absolute_error(y_test, y_pred):.4f}")
        print(f"Root Mean Squared Error (RMSE): {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(reg, model_output_path)
        print(f"Stay duration model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during stay duration model training: {e}")

def predict_stay_duration(input_data_dict, model_path='stay_duration_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        # Ensure all required columns are present in correct order
        required_columns = ['age', 'bmi', 'heart_rate', 'blood_pressure', 'diagnosis', 'treatment_type']
        
        # Create DataFrame with all required columns
        input_data = {col: input_data_dict.get(col) for col in required_columns}
        input_df = pd.DataFrame([input_data])
        
        prediction = model.predict(input_df)[0]
        
        predicted_days = max(1, round(prediction))
        
        return {
            "predicted_stay_days": int(predicted_days)
        }
        
    except FileNotFoundError:
        return {"error": "Model file (stay_duration_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during stay duration prediction: {e}"}

# ===============================================
# === HOSPITAL DISEASE FORECAST ===
# ===============================================

def train_hospital_disease_forecast_model(csv_path='hospital_disease_data.csv', model_output_path='hospital_disease_models.joblib'):
    print(f"Starting hospital disease forecast model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        required_cols = ['date', 'disease_name', 'hospital_id', 'cases']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df['date'] = pd.to_datetime(df['date'])
        df = df.rename(columns={'date': 'ds', 'cases': 'y'})
        
        models = {}
        
        for (hospital_id, disease), group_df in df.groupby(['hospital_id', 'disease_name']):
            if len(group_df) < 2: 
                print(f"Skipping {disease} for hospital {hospital_id}: not enough data points.")
                continue
                
            print(f"Training model for: {disease} at hospital {hospital_id}...")
            
            m = Prophet(yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False)
            m.fit(group_df[['ds', 'y']])
            
            models[(hospital_id, disease)] = m
            
        if not models:
            print("No models were trained. Check your data.")
            return

        print("\n--- Model: Prophet (Hospital Disease Forecast) ---")
        print(f"Successfully trained and saved {len(models)} model(s).")
        print("Models trained for combinations:")
        for key in models.keys():
            print(f"- Hospital {key[0]} / Disease {key[1]}")
        print("-" * 50 + "\n")

        joblib.dump(models, model_output_path)
        print(f"Hospital disease forecast models successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during hospital disease forecast training: {e}")

def predict_hospital_disease_forecast(input_data_dict, model_path='hospital_disease_models.joblib'):
    try:
        models = joblib.load(model_path)
        
        disease = input_data_dict.get('disease_name')
        hospital_id = int(input_data_dict.get('hospital_id'))
        days = int(input_data_dict.get('days_to_predict', 7))
        
        key = (hospital_id, disease)
        
        if key not in models:
            return {"error": f"No forecast model found for {disease} at hospital {hospital_id}. Please train the model."}
            
        m = models[key]
        future = m.make_future_dataframe(periods=days)
        forecast = m.predict(future)
        
        results = []
        forecast_data = forecast.tail(days)
        
        for index, row in forecast_data.iterrows():
            results.append({
                "date": row['ds'].strftime('%Y-%m-%d'),
                "predicted_cases": round(max(0, row['yhat'])),
            })
            
        return {
            "hospital_id": hospital_id,
            "disease_name": disease,
            "forecast": results
        }
        
    except FileNotFoundError:
        return {"error": "Model file (hospital_disease_models.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during hospital disease forecast prediction: {e}"}

# ===============================================
# === INVENTORY PREDICTION ===
# ===============================================

def train_inventory_model(csv_path='inventory_data.csv', model_output_path='inventory_prediction_model.joblib'):
    print(f"Starting inventory prediction model training with data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        
        target = 'next_week_stock'
        numerical_features = ['quantity', 'minThreshold']
        categorical_features = ['category']
        
        required_cols = numerical_features + categorical_features + [target]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must contain all of these columns: {required_cols}")
            return
            
        df = df.dropna(subset=required_cols)
        if df.empty:
            print("Error: No data to train on after cleaning.")
            return

        X = df.drop(target, axis=1)
        y = df[target]
        
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numerical_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        reg = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('regressor', RandomForestRegressor(random_state=42, n_estimators=100))
        ])
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Fitting inventory prediction pipeline...")
        reg.fit(X_train, y_train)
        
        y_pred = reg.predict(X_test)
        print("\n--- Model: RandomForestRegressor (Inventory Prediction) ---")
        print(f"R-squared (R2): {r2_score(y_test, y_pred):.4f}")
        print(f"Mean Absolute Error (MAE): {mean_absolute_error(y_test, y_pred):.4f}")
        print(f"Root Mean Squared Error (RMSE): {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
        print("-" * 50 + "\n")
        
        joblib.dump(reg, model_output_path)
        print(f"Inventory prediction model successfully saved to {model_output_path}")

    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found. Please create it first.")
    except Exception as e:
        print(f"An error occurred during inventory model training: {e}")

def predict_inventory(input_data_dict, model_path='inventory_prediction_model.joblib'):
    try:
        model = joblib.load(model_path)
        
        # Ensure all required columns are present in correct order
        required_columns = ['quantity', 'minThreshold', 'category']
        
        def _safe_int(value, fallback=0):
            try:
                if value is None:
                    return fallback
                if isinstance(value, str) and not value.strip():
                    return fallback
                return int(value)
            except (TypeError, ValueError):
                return fallback

        # Create DataFrame with all required columns
        input_data = {col: input_data_dict.get(col) for col in required_columns}
        input_data['quantity'] = _safe_int(input_data.get('quantity'))
        input_data['minThreshold'] = _safe_int(input_data.get('minThreshold'))
        if not input_data.get('category'):
            input_data['category'] = 'Consumables'
        input_df = pd.DataFrame([input_data])
        
        prediction = model.predict(input_df)[0]
        
        current_qty = _safe_int(input_data_dict.get('quantity', 0))
        min_threshold = _safe_int(input_data_dict.get('minThreshold', 0))
        category = input_data_dict.get('category', 'Consumables') or 'Consumables'
        
        # Model prediction gives us next week's stock (but we'll adjust based on current level)
        model_predicted_stock = max(0, round(prediction))
        
        # Apply a more realistic depletion based on how far item is from minimum threshold
        # Items below minimum will deplete faster
        if current_qty < min_threshold:
            # Item is already critical - assume faster depletion
            depletion_rate = 0.7  # 70% depletion per week
        elif current_qty < min_threshold * 2:
            # Item is low - moderate depletion
            depletion_rate = 0.5  # 50% depletion per week
        else:
            # Item is adequate - slower depletion
            depletion_rate = 0.3  # 30% depletion per week
        
        # Calculate predicted next week stock based on current level and depletion rate
        predicted_stock = max(0, int(current_qty * (1 - depletion_rate)))
        
        # Calculate usage rate based on the difference between current and predicted
        items_used_per_week = current_qty - predicted_stock
        usage_rate_per_day = max(0.1, round(items_used_per_week / 7, 2))
        
        # Calculate days until stockout (when inventory reaches 0)
        if usage_rate_per_day > 0 and current_qty > 0:
            days_until_stockout = max(0, int(current_qty / usage_rate_per_day))
        else:
            days_until_stockout = 999
        
        # Determine status based on current quantity vs minimum threshold and days left
        qty_ratio = current_qty / min_threshold if min_threshold > 0 else 10
        
        # Primary status decision: based on how far below/above minimum threshold
        if current_qty == 0:
            status = "Critical - Order Immediately"
            action = "urgent_reorder"
        elif current_qty <= min_threshold * 0.2:
            # Very low: 0-20% of minimum
            status = "Critical - Order Immediately"
            action = "urgent_reorder"
        elif current_qty <= min_threshold:
            # Below minimum: 20-100% of minimum
            status = "Critical - Order Immediately"
            action = "urgent_reorder"
        elif current_qty <= min_threshold * 1.5:
            # Low: 100-150% of minimum
            status = "Low - Plan Reorder"
            action = "plan_reorder"
        else:
            # Adequate: >150% of minimum
            status = "Adequate Supply"
            action = "maintain"
        
        # Secondary check: also consider predicted days
        if days_until_stockout <= 3 and status == "Adequate Supply":
            status = "Low - Plan Reorder"
            action = "plan_reorder"
        
        return {
            "item": input_data_dict.get('name', 'Unknown'),
            "item_name": input_data_dict.get('name', 'Unknown'),
            "current_quantity": current_qty,
            "predicted_next_week": int(predicted_stock),
            "minimum_threshold": min_threshold,
            "status": status,
            "stock_status": status,
            "action_required": action,
            "days_left": days_until_stockout,
            "usage_rate_per_day": f"{usage_rate_per_day:.1f}",
            "recommendation": f"Current: {current_qty}/{min_threshold} units | Next week: ~{int(predicted_stock)} | Daily usage: {usage_rate_per_day:.1f} units | {status} | Stockout in ~{days_until_stockout} days."
        }
        
    except FileNotFoundError:
        return {"error": "Model file (inventory_prediction_model.joblib) not found. Please train the model first."}
    except Exception as e:
        return {"error": f"An error occurred during inventory prediction: {e}"}

# ===============================================
# === SOS EMERGENCY SEVERITY PREDICTION ===
# ===============================================

def predict_sos_severity(input_data_dict):
    """
    Analyze emergency SOS message and predict severity level using keyword-based ML approach.
    Returns severity level (Low/Medium/High/Critical) and recommendations.
    """
    try:
        message = input_data_dict.get('message', '').lower()
        
        # Critical keywords - life-threatening
        critical_keywords = ['cardiac arrest', 'heart attack', 'stopped breathing', 'unresponsive', 
                           'severe hemorrhage', 'choking', 'unconscious', 'stroke', 'comatose',
                           'anaphylaxis', 'poisoning', 'electrocution', 'critical']
        
        # High priority keywords - serious medical emergency
        high_keywords = ['chest pain', 'difficulty breathing', 'severe pain', 'heavy bleeding',
                        'loss of consciousness', 'severe allergic', 'broken bone', 'serious injury',
                        'emergency', 'urgent', 'danger', 'severe', 'collapsed']
        
        # Medium priority keywords - moderately urgent
        medium_keywords = ['accident', 'trauma', 'injured', 'hurt', 'pain', 'bleeding',
                          'fever', 'vomiting', 'dizzy', 'weakness', 'burns', 'fracture',
                          'sprain', 'wound', 'fall']
        
        # Low priority keywords - minor issues
        low_keywords = ['cut', 'bruise', 'headache', 'nausea', 'cold', 'cough', 'rash',
                       'minor', 'slight', 'small']
        
        # Calculate severity score
        severity_score = 0
        max_score = 100
        
        # Check for critical keywords (40 points)
        if any(keyword in message for keyword in critical_keywords):
            severity_score = max(severity_score, 95)
        
        # Check for high keywords (30 points)
        elif any(keyword in message for keyword in high_keywords):
            severity_score = max(severity_score, 75)
        
        # Check for medium keywords (20 points)
        elif any(keyword in message for keyword in medium_keywords):
            severity_score = max(severity_score, 55)
        
        # Check for low keywords (10 points)
        elif any(keyword in message for keyword in low_keywords):
            severity_score = max(severity_score, 30)
        
        # Default severity if no keywords matched (based on message length/urgency)
        else:
            if len(message) > 50:
                severity_score = 40
            else:
                severity_score = 25
        
        # Determine severity level
        if severity_score >= 85:
            severity_level = "Critical"
            response_time = "1-5 minutes"
            ambulance_type = "Advanced Life Support (ALS)"
            hospital_priority = "Trauma Center"
        elif severity_score >= 70:
            severity_level = "High"
            response_time = "5-10 minutes"
            ambulance_type = "Basic Life Support (BLS)"
            hospital_priority = "Emergency Department"
        elif severity_score >= 50:
            severity_level = "Medium"
            response_time = "10-20 minutes"
            ambulance_type = "Standard Ambulance"
            hospital_priority = "Urgent Care / ED"
        else:
            severity_level = "Low"
            response_time = "20-30 minutes"
            ambulance_type = "Non-Emergency Transport"
            hospital_priority = "Clinic / Urgent Care"
        
        return {
            "severity_level": severity_level,
            "severity_score": severity_score,
            "message": message[:100],  # First 100 chars
            "response_time": response_time,
            "ambulance_type": ambulance_type,
            "hospital_type": hospital_priority,
            "ai_confidence": round(min(100, severity_score + 15), 2),
            "recommendation": f"Emergency response: {ambulance_type} dispatched with {response_time} ETA to {hospital_priority}"
        }
        
    except Exception as e:
        return {
            "error": f"An error occurred during SOS severity prediction: {e}",
            "severity_level": "Medium",
            "severity_score": 50
        }

# ===============================================
# === MAIN EXECUTION BLOCK ===
# ===============================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command provided"}))
        sys.exit(1)

    command = sys.argv[1]

    input_data = {}
    if len(sys.argv) > 2:
        try:
            arg = sys.argv[2]
            if os.path.isfile(arg):
                with open(arg, "r", encoding="utf-8") as handle:
                    input_data = json.load(handle)
            elif arg.strip().startswith('{') or arg.strip().startswith('['):
                input_data = json.loads(arg)
            else:
                input_data = {"text": arg}
        except Exception as e:
            input_data = {"text": sys.argv[2]}

    if command == "train":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else '911_calls.csv'
        train_and_save_model(csv_path=csv_file)
    elif command == "predict":
        text = input_data.get('text', '')
        print(json.dumps(predict_emergency(text)))
    elif command == "predict_eta":
        if 'end_node' not in input_data and 'hospital_name' in input_data:
            input_data['end_node'] = input_data['hospital_name']
        if 'hour' not in input_data:
            from datetime import datetime
            input_data['hour'] = datetime.now().hour
        print(json.dumps(predict_eta_route(input_data)))
    elif command == "train_eta":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'eta_data.csv'
        train_eta_model(csv_path=csv_file)
    elif command == "predict_bed_forecast":
        try:
            input_data['emergency_count'] = int(input_data.get('emergency_count', 0))
            input_data['disease_case_count'] = int(input_data.get('disease_case_count', 0))
            input_data['current_bed_occupancy'] = float(input_data.get('current_bed_occupancy', 0))
        except:
            pass
        print(json.dumps(predict_bed_forecast(input_data)))
    elif command == "train_bed_forecast":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'hospital_resource_data.csv'
        train_bed_forecast_model(csv_path=csv_file)
    elif command == "predict_staff_alloc":
        print(json.dumps(predict_staff_allocation(input_data)))
    elif command == "train_staff_alloc":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'staff_allocation_data.csv'
        train_staff_allocation_model(csv_path=csv_file)
    elif command == "predict_hosp_disease":
        print(json.dumps(predict_hospital_disease_forecast(input_data)))
    elif command == "train_hosp_disease":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'hospital_disease_data.csv'
        train_hospital_disease_forecast_model(csv_path=csv_file)
    elif command == "train_compat":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'compatibility_data.csv'
        train_compatibility_model(csv_path=csv_file)
    elif command == "predict_compat":
        print(json.dumps(predict_compatibility(input_data)))
    elif command == "train_recommend":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'hospital_data.csv'
        train_recommendation_model(csv_path=csv_file)
    elif command == "predict_recommend":
        print(json.dumps(predict_hospital_recommendation(sys.argv[2])))
    elif command == "train_risk":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'health_risk_data.csv'
        train_health_risk_model(csv_path=csv_file)
    elif command == "predict_risk":
        print(json.dumps(predict_health_risk(input_data)))
    elif command == "analyze_report":
        report_text = input_data.get("report_text") or input_data.get("text") or ""
        print(json.dumps(analyze_medical_report(report_text)))
    elif command == "train_cluster":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'user_activity_data.csv'
        train_activity_cluster_model(csv_path=csv_file)
    elif command == "predict_cluster":
        print(json.dumps(predict_activity_cluster(input_data)))
    elif command == "train_forecast":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'user_forecast_data.csv'
        train_behavior_forecast_model(csv_path=csv_file)
    elif command == "predict_forecast":
        print(json.dumps(predict_behavior_forecast(input_data)))
    elif command == "train_hotspot":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'emergency_hotspot_data.csv'
        train_emergency_hotspot_model(csv_path=csv_file)
    elif command == "predict_hotspot":
        print(json.dumps(predict_emergency_hotspots(sys.argv[2])))
    elif command == "train_forecast_outbreak":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'outbreak_data.csv'
        train_outbreak_forecast_model(csv_path=csv_file)
    elif command == "predict_forecast_outbreak":
        print(json.dumps(predict_outbreak_forecast(input_data)))
    elif command == "train_severity":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'emergency_severity_data.csv'
        train_severity_model(csv_path=csv_file)
    elif command == "predict_severity":
        print(json.dumps(predict_severity(input_data)))
    elif command == "train_availability":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'donor_availability_data.csv'
        train_availability_model(csv_path=csv_file)
    elif command == "predict_availability":
        print(json.dumps(predict_availability(input_data)))
    elif command == "train_allocation":
        model_path = sys.argv[2] if len(sys.argv) > 2 else 'allocation_q_table.joblib'
        train_allocation_model(model_output_path=model_path)
    elif command == "predict_allocation":
        print(json.dumps(predict_allocation(input_data)))
    elif command == "train_policy_seg":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'policy_data.csv'
        train_policy_segmentation_model(csv_path=csv_file)
    elif command == "predict_policy_seg":
        print(json.dumps(predict_policy_segmentation(input_data)))
    elif command == "train_perf_score":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'policy_data.csv'
        train_healthcare_performance_model(csv_path=csv_file)
    elif command == "predict_perf_score":
        print(json.dumps(predict_healthcare_performance(input_data)))
    elif command == "train_anomaly":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'anomaly_data.csv'
        train_anomaly_detection_model(csv_path=csv_file)
    elif command == "predict_anomaly":
        print(json.dumps(predict_anomaly(input_data)))
    elif command == "train_hosp_severity":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'hospital_severity_data.csv'
        train_hospital_severity_model(csv_path=csv_file)
    elif command == "predict_hosp_severity":
        print(json.dumps(predict_hospital_severity(input_data)))
    elif command == "train_hosp_perf":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'hospital_performance_data.csv'
        train_hospital_performance_model(csv_path=csv_file)
    elif command == "predict_hosp_perf":
        print(json.dumps(predict_hospital_performance(input_data)))
    elif command == "train_recovery":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'patient_outcome_data.csv'
        train_recovery_model(csv_path=csv_file)
    elif command == "predict_recovery":
        print(json.dumps(predict_recovery(input_data)))
    elif command == "train_stay":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'patient_outcome_data.csv'
        train_stay_duration_model(csv_path=csv_file)
    elif command == "predict_stay":
        print(json.dumps(predict_stay_duration(input_data)))
    elif command == "train_inventory":
        csv_file = sys.argv[2] if len(sys.argv) > 2 else 'inventory_data.csv'
        train_inventory_model(csv_path=csv_file)
    elif command == "predict_inventory":
        print(json.dumps(predict_inventory(input_data)))
    elif command == "predict_sos_severity":
        print(json.dumps(predict_sos_severity(input_data)))