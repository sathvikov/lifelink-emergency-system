import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.db.mongo import close_mongo_connection, connect_to_mongo
from app.db.asyncpg_pool import close_asyncpg, connect_asyncpg
from app.routes.admin import router as admin_router
from app.routes.alerts import router as alerts_router
from app.routes.ai import router as ai_router
from app.routes.ambulance import router as ambulance_router
from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.donors import router as donors_router
from app.routes.family import router as family_router
from app.routes.government_ops import router as government_ops_router
from app.routes.health import router as health_router
from app.routes.hospital_communication import router as hospital_communication_router
from app.routes.hospital_ml import router as hospital_ml_router
from app.routes.hospital_ops import router as hospital_ops_router
from app.routes.requests import router as requests_router
from app.routes.v2.agents import router as agents_v2_router
from app.routes.v2.analytics import router as analytics_v2_router
from app.routes.v2.ambulance import router as ambulance_v2_router
from app.routes.v2.ai_platform import router as ai_platform_v2_router
from app.routes.v2.auth import router as auth_v2_router
from app.routes.v2.gateway import router as gateway_v2_router
from app.routes.v2.government import router as government_v2_router
from app.routes.v2.government_command import router as government_command_v2_router
from app.routes.v2.hospital import router as hospital_v2_router
from app.routes.v2.integrations import router as integrations_v2_router
from app.routes.v2.ml import router as ml_v2_router
from app.routes.v2.modules import router as modules_v2_router
from app.routes.v2.notifications import router as notifications_v2_router
from app.routes.v2.public import router as public_v2_router
from app.routes.v2.rag import router as rag_v2_router
from app.routes.v2.realtime import router as realtime_v2_router
from app.routes.v2.routing import router as routing_v2_router
from app.routes.v2.search import router as search_v2_router
from app.routes.v2.users import router as users_v2_router
from app.routes.v2.system import router as system_v2_router

logger = logging.getLogger("lifelink.fastapi")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    await connect_to_mongo()
    await connect_asyncpg()
    logger.info("PostgreSQL connection initialized")
    yield
    await close_asyncpg()
    await close_mongo_connection()
    logger.info("PostgreSQL connection closed")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(health_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(ambulance_router, prefix="/api/ambulance")
app.include_router(requests_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(dashboard_router, prefix="/api/dashboard")
app.include_router(donors_router, prefix="/api")
app.include_router(family_router, prefix="/api/family")
app.include_router(government_ops_router, prefix="/api/government-ops")
app.include_router(hospital_communication_router, prefix="/api/hospital-communication")
app.include_router(hospital_ml_router, prefix="/api/hospital")
app.include_router(hospital_ml_router, prefix="/api/hosp")
app.include_router(hospital_ops_router, prefix="/api/hospital-ops")

# V2 modular service routes
app.include_router(gateway_v2_router, prefix="/v2")
app.include_router(auth_v2_router, prefix="/v2/auth")
app.include_router(users_v2_router, prefix="/v2/users")
app.include_router(hospital_v2_router, prefix="/v2/hospital")
app.include_router(ambulance_v2_router, prefix="/v2/ambulance")
app.include_router(government_v2_router, prefix="/v2/government")
app.include_router(government_command_v2_router, prefix="/v2/government")
app.include_router(agents_v2_router, prefix="/v2/agents")
app.include_router(notifications_v2_router, prefix="/v2/notifications")
app.include_router(integrations_v2_router, prefix="/v2/integrations")
app.include_router(ml_v2_router, prefix="/v2/ml")
app.include_router(rag_v2_router, prefix="/v2/rag")
app.include_router(routing_v2_router, prefix="/v2")
app.include_router(public_v2_router, prefix="/v2/public")
app.include_router(realtime_v2_router, prefix="/v2/realtime")
app.include_router(analytics_v2_router, prefix="/v2/analytics")
app.include_router(search_v2_router, prefix="/v2")
app.include_router(modules_v2_router, prefix="/v2/modules")
app.include_router(ai_platform_v2_router, prefix="/v2/ai")
app.include_router(system_v2_router, prefix="/v2/system")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation failed", "details": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
