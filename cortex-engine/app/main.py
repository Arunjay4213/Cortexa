import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import Settings
from app.limiter import limiter
from app.routes import auth, check, gate, health, memory, shield, stream

logger = logging.getLogger("cortexos")
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize NLI + attribution services
    from app.services.attributor import AttributionService
    from app.services.nli import NLIService

    nli = NLIService()
    attributor = AttributionService(nli)  # reuses same NLI instance
    app.state.nli = nli
    app.state.attributor = attributor
    app.state.settings = settings
    print("NLI service initialized (Groq API)")
    print("Attribution service initialized")

    if not settings.admin_secret:
        logger.critical(
            "\n═══════════════════════════════════════\n"
            "CORTEX_ADMIN_SECRET not set!\n"
            "Server will reject ALL requests until\n"
            "CORTEX_ADMIN_SECRET is configured.\n"
            "═══════════════════════════════════════"
        )

    # Connect to database if configured
    if settings.database_url:
        from app.db.database import create_db
        from app.db.tables import metadata

        db_factory, engine = create_db(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        app.state.db = db_factory
        print("Database connected")

    yield

    # Shutdown
    print("Shutting down")


app = FastAPI(title="CortexOS Engine", version="2.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_raw_origins = os.environ.get(
    "CORTEX_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000",
)
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(check.router)
app.include_router(gate.router)
app.include_router(health.router)
app.include_router(memory.router)
app.include_router(shield.router)
app.include_router(stream.router)
