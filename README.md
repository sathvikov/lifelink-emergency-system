# LifeLink - Smart Emergency Response and Coordination System

LifeLink is an AI-powered emergency response platform that coordinates citizens, ambulances, hospitals, and authorities in real time. It delivers fast decision support, live routing, predictive analytics, and role-based workflows with security-first design.

## Overview

LifeLink provides a unified emergency ecosystem:

- Citizens trigger SOS requests instantly
- Hospitals receive pre-arrival alerts and ETAs
- Ambulances stream live location and route updates
- Authorities monitor hotspots and run AI-assisted analytics
- ML models and Groq-powered AI assist triage and planning

## Highlights

- Groq-backed AI assistant with low-latency responses
- Real-time routing, traffic, and ETA insights
- Role-based dashboards for public, hospital, ambulance, government
- AI platform layer with inference, feature store, registry, and observability
- Federated learning flows with differential privacy
- Audit hash chain for tamper-evident system logging
- RAG semantic search with FAISS + SentenceTransformers
- WebSocket streams for live operations

## Architecture

### Frontend

- React + Vite single-page app
- Role-protected routes and dashboard tabs
- Leaflet maps for live tracking and routing visualization

### Backend

- FastAPI + Uvicorn REST APIs (legacy + v2 service routes)
- PostgreSQL with asyncpg + SQLAlchemy
- Celery + Redis for background tasks and async ML
- WebSocket streams for realtime updates

### AI and Data

- Groq API for LLM responses
- ML engine in backend/ml/ai_ml.py with joblib models
- FAISS local vector index in backend/.rag
- LangGraph multi-agent orchestration

### Free/Open-Source Integrations

- Routing: OSRM (http://router.project-osrm.org)
- Geocoding: Nominatim (OpenStreetMap)
- Weather: Open-Meteo (https://api.open-meteo.com)
- Maps: Leaflet + OpenStreetMap tiles

## Tech Stack

| Category | Technology |
|---|---|
| Frontend | React 19, Vite, React Router |
| UI and Charts | Recharts, Chart.js, react-chartjs-2, Lucide |
| Maps and Geo | Leaflet, React-Leaflet, OpenStreetMap tiles, Nominatim |
| Networking | Axios (client), httpx (server) |
| Backend | FastAPI, Uvicorn, pydantic-settings |
| Async and Jobs | Celery, Redis |
| Database | PostgreSQL, SQLAlchemy, asyncpg |
| Auth and Security | JWT (PyJWT), bcrypt, RBAC + scopes |
| AI and ML | Groq API, pandas, numpy, scikit-learn, joblib, prophet, networkx |
| Agent Orchestration | LangGraph |
| Vector Search | FAISS, SentenceTransformers |
| Realtime | WebSockets (FastAPI) |
| Routing and Weather | OSRM, Open-Meteo |

## Feature Map

### Public

- SOS emergency trigger with hospital matching
- Personal health dashboard and history
- Health risk prediction and anomaly cues
- Medical record analysis and summaries
- Donor matching and availability signals
- Nearby hospitals with ETA overlays
- Family monitoring with alerts
- LifeLink AI search and summaries

### Hospital

- Executive overview and AI insights
- Department analytics, bed management, and allocation
- Resource management and inventory forecasting
- Ambulance coordination and routing overlays
- Finance summaries, claims tracking, and analytics
- Staff roster and scheduling support
- Reports and compliance summaries
- Multi-hospital communication and mutual aid
- Live emergency feed and intake workflows

### Ambulance

- Assignment management and live navigation
- Location tracking with ETA updates
- Patient handoff summaries
- Incident escalation support
- Response history and performance stats

### Government

- National/state/district dashboards
- Emergency heatmaps and hotspot tracking
- Resource allocation and capacity signals
- Policy insights and compliance monitoring
- Audit visibility and reporting

## AI Platform (v2)

- Event streaming: /v2/ai/events/publish, /v2/ai/events/{stream}
- Feature store: /v2/ai/features/{entity_type}/{entity_id}
- Model registry: /v2/ai/registry
- Retrieval index: /v2/ai/retrieval/ingest, /v2/ai/retrieval/search
- Observability: /v2/ai/observability
- Privacy: /v2/ai/privacy/redact, /v2/ai/privacy/scan
- Synthetic data: /v2/ai/synthetic/bootstrap
- Inference: /v2/ai/infer, /v2/ai/tasks/{task_key}/infer

## ML Models Used

The ML engine uses joblib models located in backend/ml:

- health_risk_model.joblib
- emergency_severity_model.joblib
- emergency_hotspot_model.joblib
- eta_model.joblib
- bed_forecast_model.joblib
- hospital_severity_model.joblib
- hospital_disease_models.joblib
- hospital_recommendation_model.joblib
- hospital_performance_model.joblib
- healthcare_performance_model.joblib
- inventory_prediction_model.joblib
- staff_allocation_model.joblib
- donor_availability_model.joblib
- compatibility_model.joblib
- recovery_model.joblib
- stay_duration_model.joblib
- policy_segmentation_model.joblib
- outbreak_forecast_models.joblib
- anomaly_detection_model.joblib
- activity_cluster_model.joblib
- allocation_q_table.joblib
- emergency_classifier.joblib
- behavior_forecast_model.joblib

## Safety, Privacy, and Security

- JWT authentication with role-based access control and scopes
- Differential privacy for federated learning weights
- Anonymization for emergency payloads
- Redaction endpoints for sensitive data
- Audit hash chain for tamper-evident logs
- Input validation with FastAPI + pydantic
- Strict error handling with consistent JSON responses
- Server-side AI calls only (Groq key never exposed to frontend)

## Realtime WebSockets

WebSocket channels:

- ws://localhost:3010/v2/realtime/ws/ambulance
- ws://localhost:3010/v2/realtime/ws/hospital
- ws://localhost:3010/v2/realtime/ws/alerts
- ws://localhost:3010/v2/realtime/ws/government
- ws://localhost:3010/v2/realtime/ws/ai

HTTP publish helpers:

- POST /v2/realtime/ambulance-update
- POST /v2/realtime/hospital-update
- POST /v2/realtime/alert
- POST /v2/realtime/government-update

## Project Structure

```text
LifeLink-MERN-v4/
|-- client/                     # React frontend
|   |-- src/
|   |   |-- pages/              # Route-level screens
|   |   |-- components/         # Dashboard feature components
|   |   |-- context/            # Auth context
|   |   |-- config/api.js       # API base URL
|
|-- backend/                    # FastAPI backend
|   |-- app/                    # API routes and services
|   |   |-- routes/             # Legacy routes
|   |   |-- routes/v2/          # Modular service routes
|   |   |-- services/agents/    # LangGraph orchestration
|   |   |-- services/rag/       # FAISS + embeddings
|   |   |-- services/realtime/  # WebSocket manager
|   |-- .rag/                   # Local RAG index data
|   |-- ml/                     # ML engine + datasets
|   |-- scripts/                # Seeding and import utilities
|
|-- tests/                      # Parity and smoke tests
|-- docker-compose.yml          # Local deployment stack definition
|-- .dockerignore               # Docker build ignore rules
```

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11 (use .venv)
- PostgreSQL (local or cloud)
- Redis (optional, for Celery)
- Groq API key (required for backend AI)

### Install

```bash
cd client
npm install

cd ../backend
pip install -r requirements.txt
```

### Run (Windows PowerShell)

Terminal 1 (Backend):

```bash
cd backend
& "D:\Black folder\Projects\Major Project\LifeLink-MERN-v4\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 3010
```

Terminal 2 (Frontend):

```bash
cd client
npm run dev
```

Optional (Redis):

```bash
redis-server
```

Frontend: http://localhost:5000
Backend: http://localhost:3010

### Local backend startup

Use the backend helper to bootstrap schema and seed data automatically before running the FastAPI server:

```bash
cd backend
bash start.sh
```

### Run with Docker Compose

```bash
docker compose up --build
```

This starts the backend, frontend, PostgreSQL, and Redis services together.

## Environment Variables

### backend/.env

- POSTGRES_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/lifelink_db
- JWT_SECRET=replace_with_secure_secret
- FRONTEND_URL=http://localhost:5000
- APP_ENV=development
- REDIS_URL=redis://localhost:6379/0
- CELERY_BROKER_URL=redis://localhost:6379/0
- CELERY_RESULT_BACKEND=redis://localhost:6379/1
- LLM_PROVIDER=groq
- GROQ_API_KEY=replace_with_your_groq_api_key
- GROQ_BASE_URL=https://api.groq.com
- GROQ_MODEL=llama3-8b-8192
- EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
- RAG_TOP_K=5
- PYTHON_PATH=optional absolute python path

### client/.env

- VITE_API_URL=http://localhost:3010

## Data Import and Seeding

### Seed PostgreSQL demo data (synthetic)

Generates hospitals, ambulances, and public users with donor profiles.

```bash
python backend/scripts/seed_postgres_data.py
```

### Import hospital locations (data.gov.in or Kaggle CSV)

```bash
python backend/scripts/import_hospital_locations.py --input "D:\path\to\hospitals.csv" --drop
```

If your CSV uses different column names:

```bash
python backend/scripts/import_hospital_locations.py --input "D:\path\to\hospitals.csv" --name-col HospitalName --lat-col Latitude --lng-col Longitude --allow-fallback
```

## Deployment

### Backend on Render (single service)

- Render service definition is included in [render.yaml](render.yaml).
- The backend now uses `backend/start.sh` to bootstrap SQL schema and demo data automatically before starting the FastAPI server.
- The service runs FastAPI on the Render-provided `PORT` and uses a single PostgreSQL database.
- Configure the environment variables in Render (values are defined in the render.yaml template):
	- `POSTGRES_URL`
	- `JWT_SECRET`
	- `GROQ_API_KEY`
	- `FRONTEND_URL` (your Vercel URL)
	- `REDIS_URL` (optional)

### Frontend on Vercel

- Vercel SPA rewrite rules are defined in [client/vercel.json](client/vercel.json).
- Set `VITE_API_URL` in Vercel to your Render backend URL.

### Notes

- Redis is optional; in-memory caching is used if Redis is unavailable.
- All AI calls run through the FastAPI backend; the Groq API key is never exposed to the frontend.

## Testing

```bash
python -m pytest tests
```

## Use Cases

- Road accidents
- Cardiac emergencies
- Stroke response
- Elderly care escalation
- Smart city emergency command workflows

## Author

Maharaj
B.E. CSE - Sahyadri College of Engineering
