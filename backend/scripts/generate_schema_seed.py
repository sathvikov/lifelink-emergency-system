import csv
import os
from datetime import datetime

ROOT = "d:/Black folder/Projects/Major Project/LifeLink-MERN-v4"
ML_DIR = os.path.join(ROOT, "backend", "ml")
SCRIPTS_DIR = os.path.join(ROOT, "backend", "scripts")

os.makedirs(SCRIPTS_DIR, exist_ok=True)

schema_lines = [
    "-- Auto-generated schema for LifeLink v1\n",
    "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";\n",
    "\n-- Core document store\n",
    "CREATE TABLE IF NOT EXISTS documents (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    collection VARCHAR(120) NOT NULL,\n"
    "    data JSONB NOT NULL,\n"
    "    created_at TIMESTAMPTZ NOT NULL,\n"
    "    updated_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents (collection);\n",
    "CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at);\n",
    "CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents (updated_at);\n",
    "\n-- Government command center tables\n",
    "CREATE TABLE IF NOT EXISTS gov_hospitals (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    name VARCHAR(200) NOT NULL,\n"
    "    city VARCHAR(120),\n"
    "    state VARCHAR(120),\n"
    "    latitude DOUBLE PRECISION NOT NULL,\n"
    "    longitude DOUBLE PRECISION NOT NULL,\n"
    "    status VARCHAR(40) DEFAULT 'active',\n"
    "    verified BOOLEAN DEFAULT FALSE,\n"
    "    beds_total INTEGER DEFAULT 0,\n"
    "    beds_available INTEGER DEFAULT 0,\n"
    "    load_score DOUBLE PRECISION DEFAULT 0.0,\n"
    "    rating DOUBLE PRECISION DEFAULT 4.0,\n"
    "    created_at TIMESTAMPTZ NOT NULL,\n"
    "    updated_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "CREATE INDEX IF NOT EXISTS idx_gov_hospitals_city ON gov_hospitals (city);\n",
    "CREATE INDEX IF NOT EXISTS idx_gov_hospitals_verified ON gov_hospitals (verified);\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_ambulances (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    code VARCHAR(60) NOT NULL,\n"
    "    driver VARCHAR(120),\n"
    "    latitude DOUBLE PRECISION NOT NULL,\n"
    "    longitude DOUBLE PRECISION NOT NULL,\n"
    "    status VARCHAR(40) DEFAULT 'available',\n"
    "    verified BOOLEAN DEFAULT FALSE,\n"
    "    created_at TIMESTAMPTZ NOT NULL,\n"
    "    updated_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "CREATE INDEX IF NOT EXISTS idx_gov_ambulances_status ON gov_ambulances (status);\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_emergencies (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    emergency_type VARCHAR(120) NOT NULL,\n"
    "    severity VARCHAR(40) NOT NULL,\n"
    "    latitude DOUBLE PRECISION NOT NULL,\n"
    "    longitude DOUBLE PRECISION NOT NULL,\n"
    "    status VARCHAR(40) DEFAULT 'active',\n"
    "    hospital_id VARCHAR(40) REFERENCES gov_hospitals(id),\n"
    "    ambulance_id VARCHAR(40) REFERENCES gov_ambulances(id),\n"
    "    occurred_at TIMESTAMPTZ NOT NULL,\n"
    "    created_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "CREATE INDEX IF NOT EXISTS idx_gov_emergencies_severity ON gov_emergencies (severity);\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_users (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    role VARCHAR(40) NOT NULL,\n"
    "    sub_role VARCHAR(60),\n"
    "    latitude DOUBLE PRECISION,\n"
    "    longitude DOUBLE PRECISION,\n"
    "    created_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_predictions (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    prediction_type VARCHAR(80) NOT NULL,\n"
    "    result JSONB NOT NULL,\n"
    "    confidence DOUBLE PRECISION DEFAULT 0.0,\n"
    "    created_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_verification_requests (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    entity_type VARCHAR(40) NOT NULL,\n"
    "    entity_id VARCHAR(40) NOT NULL,\n"
    "    status VARCHAR(30) DEFAULT 'pending',\n"
    "    notes TEXT,\n"
    "    requested_by VARCHAR(40),\n"
    "    reviewed_by VARCHAR(40),\n"
    "    reviewed_at TIMESTAMPTZ,\n"
    "    created_at TIMESTAMPTZ NOT NULL,\n"
    "    updated_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "CREATE INDEX IF NOT EXISTS idx_gov_verification_status ON gov_verification_requests (status);\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_audit_logs (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    action VARCHAR(80) NOT NULL,\n"
    "    actor_id VARCHAR(40) NOT NULL,\n"
    "    entity_type VARCHAR(40) NOT NULL,\n"
    "    entity_id VARCHAR(40) NOT NULL,\n"
    "    details JSONB NOT NULL,\n"
    "    created_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_disaster_events (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    disaster_type VARCHAR(80) NOT NULL,\n"
    "    status VARCHAR(40) NOT NULL,\n"
    "    zone VARCHAR(120),\n"
    "    severity VARCHAR(40) NOT NULL,\n"
    "    started_at TIMESTAMPTZ NOT NULL,\n"
    "    peak_at TIMESTAMPTZ,\n"
    "    resolved_at TIMESTAMPTZ,\n"
    "    timeline JSONB NOT NULL,\n"
    "    metadata JSONB NOT NULL,\n"
    "    created_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_decision_events (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    event VARCHAR(120) NOT NULL,\n"
    "    location VARCHAR(120),\n"
    "    reason TEXT NOT NULL,\n"
    "    confidence DOUBLE PRECISION DEFAULT 0.0,\n"
    "    suggested_action TEXT NOT NULL,\n"
    "    impact VARCHAR(40) NOT NULL,\n"
    "    affected_entities JSONB NOT NULL,\n"
    "    created_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_policy_actions (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    title VARCHAR(200) NOT NULL,\n"
    "    action TEXT NOT NULL,\n"
    "    status VARCHAR(40) NOT NULL,\n"
    "    impact VARCHAR(40),\n"
    "    decision_event_id VARCHAR(40),\n"
    "    created_at TIMESTAMPTZ NOT NULL,\n"
    "    updated_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_simulation_sessions (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    status VARCHAR(40) NOT NULL,\n"
    "    intensity VARCHAR(40) DEFAULT 'medium',\n"
    "    started_at TIMESTAMPTZ NOT NULL,\n"
    "    ended_at TIMESTAMPTZ,\n"
    "    metadata JSONB NOT NULL\n"
    ");\n",
    "\n",
    "CREATE TABLE IF NOT EXISTS gov_knowledge_base (\n"
    "    id VARCHAR(40) PRIMARY KEY,\n"
    "    module VARCHAR(120) NOT NULL,\n"
    "    title VARCHAR(240) NOT NULL,\n"
    "    content TEXT NOT NULL,\n"
    "    tags JSONB NOT NULL,\n"
    "    source VARCHAR(120),\n"
    "    created_at TIMESTAMPTZ NOT NULL,\n"
    "    updated_at TIMESTAMPTZ NOT NULL\n"
    ");\n",
]

seed_lines = ["-- Auto-generated seed script for LifeLink v1\n", "BEGIN;\n"]

now = datetime.utcnow().isoformat()

seed_lines.extend([
    "-- Minimal seed for command center tables\n",
    "INSERT INTO gov_hospitals (id, name, city, state, latitude, longitude, status, verified, beds_total, beds_available, load_score, rating, created_at, updated_at) VALUES\n"
    f"('seed-hosp-1','Central Medical','Metro','State',12.9716,77.5946,'active',true,180,40,0.78,4.6,'{now}','{now}'),\n"
    f"('seed-hosp-2','Harbor Health','Metro','State',12.9816,77.6046,'active',false,140,28,0.80,4.2,'{now}','{now}')\n"
    "ON CONFLICT DO NOTHING;\n",
    "INSERT INTO gov_ambulances (id, code, driver, latitude, longitude, status, verified, created_at, updated_at) VALUES\n"
    f"('seed-amb-1','AMB-2001','Driver One',12.975,77.59,'available',true,'{now}','{now}'),\n"
    f"('seed-amb-2','AMB-2002','Driver Two',12.965,77.61,'assigned',false,'{now}','{now}')\n"
    "ON CONFLICT DO NOTHING;\n",
    "INSERT INTO gov_emergencies (id, emergency_type, severity, latitude, longitude, status, hospital_id, ambulance_id, occurred_at, created_at) VALUES\n"
    f"('seed-em-1','road_accident','High',12.968,77.592,'active',NULL,NULL,'{now}','{now}'),\n"
    f"('seed-em-2','cardiac','Critical',12.974,77.599,'active',NULL,NULL,'{now}','{now}')\n"
    "ON CONFLICT DO NOTHING;\n",
    "\n",
])

csv_files = [f for f in os.listdir(ML_DIR) if f.lower().endswith('.csv')]

for csv_file in sorted(csv_files):
    table_name = "ml_" + "".join([c if c.isalnum() else "_" for c in os.path.splitext(csv_file)[0].lower()])
    csv_path = os.path.join(ML_DIR, csv_file).replace("\\", "/")
    with open(os.path.join(ML_DIR, csv_file), newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            headers = []
    if not headers:
        continue
    cols = []
    for col in headers:
        name = col.strip().replace('"', '""')
        cols.append(f'"{name}" TEXT')
    schema_lines.append(f"\n-- ML dataset: {csv_file}\n")
    schema_lines.append(
        "CREATE TABLE IF NOT EXISTS {table} (\n    id BIGSERIAL PRIMARY KEY,\n    {cols}\n);\n".format(
            table=table_name,
            cols=",\n    ".join(cols),
        )
    )

    header_list = "\", \"".join([h.replace('"', '""') for h in headers])
    seed_lines.append(
        f"\\copy {table_name} (\"{header_list}\") FROM '{csv_path}' WITH (FORMAT csv, HEADER true);\n"
    )

seed_lines.append("COMMIT;\n")

schema_path = os.path.join(SCRIPTS_DIR, "schema.sql")
seed_path = os.path.join(SCRIPTS_DIR, "seed.sql")

with open(schema_path, "w", encoding="utf-8") as f:
    f.writelines(schema_lines)

with open(seed_path, "w", encoding="utf-8") as f:
    f.writelines(seed_lines)

print("Generated:", schema_path)
print("Generated:", seed_path)
print("CSV tables:", len(csv_files))
