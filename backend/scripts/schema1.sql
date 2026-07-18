-- Public and hospital schema for LifeLink v1
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Public domain tables
CREATE TABLE IF NOT EXISTS public_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(240) UNIQUE NOT NULL,
    phone VARCHAR(40),
    age INTEGER,
    gender VARCHAR(20),
    blood_group VARCHAR(5),
    city VARCHAR(120),
    state VARCHAR(120),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_public_users_city ON public_users (city);

CREATE TABLE IF NOT EXISTS public_donor_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public_users(id) ON DELETE CASCADE,
    availability VARCHAR(40) NOT NULL DEFAULT 'Available',
    organ_types JSONB NOT NULL DEFAULT '[]',
    last_donation DATE,
    donor_since DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_public_donors_user ON public_donor_profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_public_donors_availability ON public_donor_profiles (availability);

CREATE TABLE IF NOT EXISTS public_sos_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public_users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    eta_minutes INTEGER,
    assigned_hospital_id UUID,
    assigned_ambulance_code VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_public_sos_user ON public_sos_requests (user_id);
CREATE INDEX IF NOT EXISTS idx_public_sos_severity ON public_sos_requests (severity);

CREATE TABLE IF NOT EXISTS public_health_risk_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public_users(id) ON DELETE CASCADE,
    risk_level VARCHAR(20) NOT NULL,
    risk_score INTEGER NOT NULL,
    bmi NUMERIC(5, 2),
    blood_pressure INTEGER,
    heart_rate INTEGER,
    lifestyle_factor VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_public_risk_user ON public_health_risk_assessments (user_id);

CREATE TABLE IF NOT EXISTS public_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public_users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    read BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_public_notifications_user ON public_notifications (user_id);
CREATE INDEX IF NOT EXISTS idx_public_notifications_read ON public_notifications (read);

-- Hospital domain tables
CREATE TABLE IF NOT EXISTS hospital_facilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    city VARCHAR(120),
    state VARCHAR(120),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    rating NUMERIC(2, 1) DEFAULT 4.0,
    beds_total INTEGER DEFAULT 0,
    beds_available INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hospital_facilities_city ON hospital_facilities (city);

CREATE TABLE IF NOT EXISTS hospital_departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id UUID NOT NULL REFERENCES hospital_facilities(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    head VARCHAR(120),
    phone VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hospital_departments_hospital ON hospital_departments (hospital_id);

CREATE TABLE IF NOT EXISTS hospital_staff (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id UUID NOT NULL REFERENCES hospital_facilities(id) ON DELETE CASCADE,
    department_id UUID REFERENCES hospital_departments(id) ON DELETE SET NULL,
    full_name VARCHAR(200) NOT NULL,
    role VARCHAR(80) NOT NULL,
    shift VARCHAR(40),
    availability BOOLEAN NOT NULL DEFAULT TRUE,
    certifications JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hospital_staff_hospital ON hospital_staff (hospital_id);
CREATE INDEX IF NOT EXISTS idx_hospital_staff_role ON hospital_staff (role);

CREATE TABLE IF NOT EXISTS hospital_beds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id UUID NOT NULL REFERENCES hospital_facilities(id) ON DELETE CASCADE,
    bed_type VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Available',
    patient_name VARCHAR(120),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hospital_beds_hospital ON hospital_beds (hospital_id);
CREATE INDEX IF NOT EXISTS idx_hospital_beds_status ON hospital_beds (status);

CREATE TABLE IF NOT EXISTS hospital_equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id UUID NOT NULL REFERENCES hospital_facilities(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    category VARCHAR(80),
    quantity INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'Operational',
    min_threshold INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hospital_equipment_hospital ON hospital_equipment (hospital_id);

CREATE TABLE IF NOT EXISTS hospital_emergency_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id UUID NOT NULL REFERENCES hospital_facilities(id) ON DELETE CASCADE,
    patient_name VARCHAR(120),
    symptoms TEXT,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Active',
    source VARCHAR(30) NOT NULL DEFAULT 'public',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hospital_emergency_hospital ON hospital_emergency_events (hospital_id);
CREATE INDEX IF NOT EXISTS idx_hospital_emergency_severity ON hospital_emergency_events (severity);

-- High-performance operational tables (add-on layer)
CREATE TABLE IF NOT EXISTS hospitals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    location VARCHAR(240) NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    occupancy INTEGER NOT NULL DEFAULT 0,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hospitals_location ON hospitals (location);

CREATE TABLE IF NOT EXISTS ambulances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver VARCHAR(160),
    location VARCHAR(240) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'available',
    verified BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_ambulances_location ON ambulances (location);
CREATE INDEX IF NOT EXISTS idx_ambulances_status ON ambulances (status);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role VARCHAR(40) NOT NULL,
    location VARCHAR(240)
);
CREATE INDEX IF NOT EXISTS idx_users_location ON users (location);

CREATE TABLE IF NOT EXISTS emergencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type VARCHAR(80) NOT NULL,
    severity VARCHAR(40) NOT NULL,
    location VARCHAR(240) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_hospital UUID
);
CREATE INDEX IF NOT EXISTS idx_emergencies_location ON emergencies (location);
CREATE INDEX IF NOT EXISTS idx_emergencies_timestamp ON emergencies (timestamp);
CREATE INDEX IF NOT EXISTS idx_emergencies_status ON emergencies (status);

CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_type VARCHAR(80) NOT NULL,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions (created_at);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(120) NOT NULL,
    actor VARCHAR(120) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    hash VARCHAR(128) NOT NULL,
    prev_hash VARCHAR(128)
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp);
