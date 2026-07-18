-- Auto-generated seed script for LifeLink v1
BEGIN;
-- Minimal seed for command center tables
INSERT INTO gov_hospitals (id, name, city, state, latitude, longitude, status, verified, beds_total, beds_available, load_score, rating, created_at, updated_at) VALUES
('seed-hosp-1','Central Medical','Metro','State',12.9716,77.5946,'active',true,180,40,0.78,4.6,'2026-04-04T16:43:12.496893','2026-04-04T16:43:12.496893'),
('seed-hosp-2','Harbor Health','Metro','State',12.9816,77.6046,'active',false,140,28,0.80,4.2,'2026-04-04T16:43:12.496893','2026-04-04T16:43:12.496893')
ON CONFLICT DO NOTHING;
INSERT INTO gov_ambulances (id, code, driver, latitude, longitude, status, verified, created_at, updated_at) VALUES
('seed-amb-1','AMB-2001','Driver One',12.975,77.59,'available',true,'2026-04-04T16:43:12.496893','2026-04-04T16:43:12.496893'),
('seed-amb-2','AMB-2002','Driver Two',12.965,77.61,'assigned',false,'2026-04-04T16:43:12.496893','2026-04-04T16:43:12.496893')
ON CONFLICT DO NOTHING;
INSERT INTO gov_emergencies (id, emergency_type, severity, latitude, longitude, status, hospital_id, ambulance_id, occurred_at, created_at) VALUES
('seed-em-1','road_accident','High',12.968,77.592,'active',NULL,NULL,'2026-04-04T16:43:12.496893','2026-04-04T16:43:12.496893'),
('seed-em-2','cardiac','Critical',12.974,77.599,'active',NULL,NULL,'2026-04-04T16:43:12.496893','2026-04-04T16:43:12.496893')
ON CONFLICT DO NOTHING;

\copy ml_911_calls ("lat", "lng", "desc", "zip", "title", "timeStamp", "twp", "addr", "e") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/911_calls.csv' WITH (FORMAT csv, HEADER true);
\copy ml_anomaly_data ("region", "daily_emergency_count", "hospital_admissions", "disease_reports") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/anomaly_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_compatibility_data ("receiver_blood_type", "receiver_age", "receiver_gender", "donor_blood_type", "donor_age", "donor_gender", "organ_type", "location_distance", "is_compatible") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/compatibility_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_donor_availability_data ("region", "month", "resource_type", "donation_frequency", "hospital_stock_level", "future_availability_score") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/donor_availability_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_emergency_hotspot_data ("lat", "lng", "emergency_type", "severity", "timestamp") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/emergency_hotspot_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_emergency_severity_data ("emergency_type", "region", "population_density", "avg_response_time_min", "severity") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/emergency_severity_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_eta_data ("hour", "start_region", "end_region", "traffic_multiplier") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/eta_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_health_risk_data ("Patient ID", "Age", "Sex", "Cholesterol", "Blood Pressure", "Heart Rate", "Diabetes", "Family History", "Smoking", "Obesity", "Alcohol Consumption", "Exercise Hours Per Week", "Diet", "Previous Heart Problems", "Medication Use", "Stress Level", "Sedentary Hours Per Day", "Income", "BMI", "Triglycerides", "Physical Activity Days Per Week", "Sleep Hours Per Day", "Country", "Continent", "Hemisphere", "Heart Attack Risk") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/health_risk_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_hospital_data ("emergency_type", "distance_km", "traffic_level", "hospital_rating", "is_best_choice") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/hospital_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_hospital_disease_data ("date", "disease_name", "hospital_id", "cases") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/hospital_disease_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_hospital_performance_data ("hospital_id", "avg_response_time", "treatment_success_rate", "patient_satisfaction", "resource_utilization") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/hospital_performance_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_hospital_resource_data ("hospital_id", "emergency_count", "disease_case_count", "current_bed_occupancy", "next_week_bed_demand") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/hospital_resource_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_hospital_severity_data ("emergency_type", "age", "heart_rate", "blood_pressure_systolic", "distance_km", "severity") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/hospital_severity_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_inventory_data ("name", "quantity", "category", "minThreshold", "next_week_stock") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/inventory_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_outbreak_data ("date", "disease_name", "region", "cases") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/outbreak_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_patient_outcome_data ("age", "bmi", "heart_rate", "blood_pressure", "diagnosis", "treatment_type", "recovered", "stay_duration_days") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/patient_outcome_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_policy_data ("region", "emergency_rate", "avg_response_time", "hospital_bed_occupancy", "health_outcome_score") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/policy_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_staff_allocation_data ("patient_load", "department", "shift", "allocation_decision") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/staff_allocation_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_user_activity_data ("sos_usage", "donations_made", "health_logs") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/user_activity_data.csv' WITH (FORMAT csv, HEADER true);
\copy ml_user_forecast_data ("past_donations", "future_donations") FROM 'd:/Black folder/Projects/Major Project/LifeLink-MERN-v4/backend/ml/user_forecast_data.csv' WITH (FORMAT csv, HEADER true);
COMMIT;
