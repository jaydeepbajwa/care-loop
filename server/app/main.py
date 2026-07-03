from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .logging_setup import configure_logging
from .middleware import RequestLogMiddleware
from .routers import careteam, checkins, enrollment, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all instead of migrations — a deliberate demo-scope tradeoff,
    # documented in README "Honest limits". Production would use Alembic.
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="CareLoop API",
        description="Member enrollment, symptom check-ins, and human-in-the-loop triage.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLogMiddleware)
    # Vite dev server origin; in docker-compose nginx proxies /api same-origin
    # so CORS never fires there.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(enrollment.router)
    app.include_router(checkins.router)
    app.include_router(careteam.router)
    return app


app = create_app()
