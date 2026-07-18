-- Auto-generated schema for LifeLink v1
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core document store
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(40) PRIMARY KEY,
    collection VARCHAR(120) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents (collection);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at);
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents (updated_at);

-- Government command center tables
CREATE TABLE IF NOT EXISTS gov_hospitals (
    id VARCHAR(40) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(120),
    state VARCHAR(120),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    status VARCHAR(40) DEFAULT 'active',
    verified BOOLEAN DEFAULT FALSE,
    beds_total INTEGER DEFAULT 0,
    beds_available INTEGER DEFAULT 0,
    load_score DOUBLE PRECISION DEFAULT 0.0,
    rating DOUBLE PRECISION DEFAULT 4.0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gov_hospitals_city ON gov_hospitals (city);
CREATE INDEX IF NOT EXISTS idx_gov_hospitals_verified ON gov_hospitals (verified);

CREATE TABLE IF NOT EXISTS gov_ambulances (
    id VARCHAR(40) PRIMARY KEY,
    code VARCHAR(60) NOT NULL,
    driver VARCHAR(120),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    status VARCHAR(40) DEFAULT 'available',
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gov_ambulances_status ON gov_ambulances (status);

CREATE TABLE IF NOT EXISTS gov_emergencies (
    id VARCHAR(40) PRIMARY KEY,
    emergency_type VARCHAR(120) NOT NULL,
    severity VARCHAR(40) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    status VARCHAR(40) DEFAULT 'active',
    hospital_id VARCHAR(40) REFERENCES gov_hospitals(id),
    ambulance_id VARCHAR(40) REFERENCES gov_ambulances(id),
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gov_emergencies_severity ON gov_emergencies (severity);

CREATE TABLE IF NOT EXISTS gov_users (
    id VARCHAR(40) PRIMARY KEY,
    role VARCHAR(40) NOT NULL,
    sub_role VARCHAR(60),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_predictions (
    id VARCHAR(40) PRIMARY KEY,
    prediction_type VARCHAR(80) NOT NULL,
    result JSONB NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_verification_requests (
    id VARCHAR(40) PRIMARY KEY,
    entity_type VARCHAR(40) NOT NULL,
    entity_id VARCHAR(40) NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',
    notes TEXT,
    requested_by VARCHAR(40),
    reviewed_by VARCHAR(40),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gov_verification_status ON gov_verification_requests (status);

CREATE TABLE IF NOT EXISTS gov_audit_logs (
    id VARCHAR(40) PRIMARY KEY,
    action VARCHAR(80) NOT NULL,
    actor_id VARCHAR(40) NOT NULL,
    entity_type VARCHAR(40) NOT NULL,
    entity_id VARCHAR(40) NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_disaster_events (
    id VARCHAR(40) PRIMARY KEY,
    disaster_type VARCHAR(80) NOT NULL,
    status VARCHAR(40) NOT NULL,
    zone VARCHAR(120),
    severity VARCHAR(40) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    peak_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    timeline JSONB NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_decision_events (
    id VARCHAR(40) PRIMARY KEY,
    event VARCHAR(120) NOT NULL,
    location VARCHAR(120),
    reason TEXT NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 0.0,
    suggested_action TEXT NOT NULL,
    impact VARCHAR(40) NOT NULL,
    affected_entities JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_policy_actions (
    id VARCHAR(40) PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    action TEXT NOT NULL,
    status VARCHAR(40) NOT NULL,
    impact VARCHAR(40),
    decision_event_id VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS gov_simulation_sessions (
    id VARCHAR(40) PRIMARY KEY,
    status VARCHAR(40) NOT NULL,
    intensity VARCHAR(40) DEFAULT 'medium',
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    metadata JSONB NOT NULL
);

-- ML dataset: 911_calls.csv
CREATE TABLE IF NOT EXISTS ml_911_calls (
    id BIGSERIAL PRIMARY KEY,
    "lat" TEXT,
    "lng" TEXT,
    "desc" TEXT,
    "zip" TEXT,
    "title" TEXT,
    "timeStamp" TEXT,
    "twp" TEXT,
    "addr" TEXT,
    "e" TEXT
);

-- ML dataset: anomaly_data.csv
CREATE TABLE IF NOT EXISTS ml_anomaly_data (
    id BIGSERIAL PRIMARY KEY,
    "region" TEXT,
    "daily_emergency_count" TEXT,
    "hospital_admissions" TEXT,
    "disease_reports" TEXT
);

-- ML dataset: compatibility_data.csv
CREATE TABLE IF NOT EXISTS ml_compatibility_data (
    id BIGSERIAL PRIMARY KEY,
    "receiver_blood_type" TEXT,
    "receiver_age" TEXT,
    "receiver_gender" TEXT,
    "donor_blood_type" TEXT,
    "donor_age" TEXT,
    "donor_gender" TEXT,
    "organ_type" TEXT,
    "location_distance" TEXT,
    "is_compatible" TEXT
);

-- ML dataset: donor_availability_data.csv
CREATE TABLE IF NOT EXISTS ml_donor_availability_data (
    id BIGSERIAL PRIMARY KEY,
    "region" TEXT,
    "month" TEXT,
    "resource_type" TEXT,
    "donation_frequency" TEXT,
    "hospital_stock_level" TEXT,
    "future_availability_score" TEXT
);

-- ML dataset: emergency_hotspot_data.csv
CREATE TABLE IF NOT EXISTS ml_emergency_hotspot_data (
    id BIGSERIAL PRIMARY KEY,
    "lat" TEXT,
    "lng" TEXT,
    "emergency_type" TEXT,
    "severity" TEXT,
    "timestamp" TEXT
);

-- ML dataset: emergency_severity_data.csv
CREATE TABLE IF NOT EXISTS ml_emergency_severity_data (
    id BIGSERIAL PRIMARY KEY,
    "emergency_type" TEXT,
    "region" TEXT,
    "population_density" TEXT,
    "avg_response_time_min" TEXT,
    "severity" TEXT
);

-- ML dataset: eta_data.csv
CREATE TABLE IF NOT EXISTS ml_eta_data (
    id BIGSERIAL PRIMARY KEY,
    "hour" TEXT,
    "start_region" TEXT,
    "end_region" TEXT,
    "traffic_multiplier" TEXT
);

-- ML dataset: health_risk_data.csv
CREATE TABLE IF NOT EXISTS ml_health_risk_data (
    id BIGSERIAL PRIMARY KEY,
    "Patient ID" TEXT,
    "Age" TEXT,
    "Sex" TEXT,
    "Cholesterol" TEXT,
    "Blood Pressure" TEXT,
    "Heart Rate" TEXT,
    "Diabetes" TEXT,
    "Family History" TEXT,
    "Smoking" TEXT,
    "Obesity" TEXT,
    "Alcohol Consumption" TEXT,
    "Exercise Hours Per Week" TEXT,
    "Diet" TEXT,
    "Previous Heart Problems" TEXT,
    "Medication Use" TEXT,
    "Stress Level" TEXT,
    "Sedentary Hours Per Day" TEXT,
    "Income" TEXT,
    "BMI" TEXT,
    "Triglycerides" TEXT,
    "Physical Activity Days Per Week" TEXT,
    "Sleep Hours Per Day" TEXT,
    "Country" TEXT,
    "Continent" TEXT,
    "Hemisphere" TEXT,
    "Heart Attack Risk" TEXT
);

-- ML dataset: hospital_data.csv
CREATE TABLE IF NOT EXISTS ml_hospital_data (
    id BIGSERIAL PRIMARY KEY,
    "emergency_type" TEXT,
    "distance_km" TEXT,
    "traffic_level" TEXT,
    "hospital_rating" TEXT,
    "is_best_choice" TEXT
);

-- ML dataset: hospital_disease_data.csv
CREATE TABLE IF NOT EXISTS ml_hospital_disease_data (
    id BIGSERIAL PRIMARY KEY,
    "date" TEXT,
    "disease_name" TEXT,
    "hospital_id" TEXT,
    "cases" TEXT
);

-- ML dataset: hospital_performance_data.csv
CREATE TABLE IF NOT EXISTS ml_hospital_performance_data (
    id BIGSERIAL PRIMARY KEY,
    "hospital_id" TEXT,
    "avg_response_time" TEXT,
    "treatment_success_rate" TEXT,
    "patient_satisfaction" TEXT,
    "resource_utilization" TEXT
);

-- ML dataset: hospital_resource_data.csv
CREATE TABLE IF NOT EXISTS ml_hospital_resource_data (
    id BIGSERIAL PRIMARY KEY,
    "hospital_id" TEXT,
    "emergency_count" TEXT,
    "disease_case_count" TEXT,
    "current_bed_occupancy" TEXT,
    "next_week_bed_demand" TEXT
);

-- ML dataset: hospital_severity_data.csv
CREATE TABLE IF NOT EXISTS ml_hospital_severity_data (
    id BIGSERIAL PRIMARY KEY,
    "emergency_type" TEXT,
    "age" TEXT,
    "heart_rate" TEXT,
    "blood_pressure_systolic" TEXT,
    "distance_km" TEXT,
    "severity" TEXT
);

-- ML dataset: inventory_data.csv
CREATE TABLE IF NOT EXISTS ml_inventory_data (
    id BIGSERIAL PRIMARY KEY,
    "name" TEXT,
    "quantity" TEXT,
    "category" TEXT,
    "minThreshold" TEXT,
    "next_week_stock" TEXT
);

-- ML dataset: outbreak_data.csv
CREATE TABLE IF NOT EXISTS ml_outbreak_data (
    id BIGSERIAL PRIMARY KEY,
    "date" TEXT,
    "disease_name" TEXT,
    "region" TEXT,
    "cases" TEXT
);

-- ML dataset: patient_outcome_data.csv
CREATE TABLE IF NOT EXISTS ml_patient_outcome_data (
    id BIGSERIAL PRIMARY KEY,
    "age" TEXT,
    "bmi" TEXT,
    "heart_rate" TEXT,
    "blood_pressure" TEXT,
    "diagnosis" TEXT,
    "treatment_type" TEXT,
    "recovered" TEXT,
    "stay_duration_days" TEXT
);

-- ML dataset: policy_data.csv
CREATE TABLE IF NOT EXISTS ml_policy_data (
    id BIGSERIAL PRIMARY KEY,
    "region" TEXT,
    "emergency_rate" TEXT,
    "avg_response_time" TEXT,
    "hospital_bed_occupancy" TEXT,
    "health_outcome_score" TEXT
);

-- ML dataset: staff_allocation_data.csv
CREATE TABLE IF NOT EXISTS ml_staff_allocation_data (
    id BIGSERIAL PRIMARY KEY,
    "patient_load" TEXT,
    "department" TEXT,
    "shift" TEXT,
    "allocation_decision" TEXT
);

-- ML dataset: user_activity_data.csv
CREATE TABLE IF NOT EXISTS ml_user_activity_data (
    id BIGSERIAL PRIMARY KEY,
    "sos_usage" TEXT,
    "donations_made" TEXT,
    "health_logs" TEXT
);

-- ML dataset: user_forecast_data.csv
CREATE TABLE IF NOT EXISTS ml_user_forecast_data (
    id BIGSERIAL PRIMARY KEY,
    "past_donations" TEXT,
    "future_donations" TEXT
);
