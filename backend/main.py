import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from .routers import systems, assets, columns, glossary, ingest, lineage, search, classification
from . import security as security_module
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CDGC-Lite API")
# CORS for local dev UI
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional OpenTelemetry instrumentation
if os.getenv("OTEL_ENABLED") == "1":
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        # Non-fatal if OTEL packages are unavailable
        pass

# Optional OpenTelemetry instrumentation
if os.getenv("OTEL_ENABLED") == "1":
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from .db import engine

        FastAPIInstrumentor.instrument_app(app)
        try:
            SQLAlchemyInstrumentor().instrument(engine=engine)
        except Exception:
            # If engine not yet created, instrument default
            SQLAlchemyInstrumentor().instrument()
    except Exception:
        pass

app.include_router(systems.router)
app.include_router(assets.router)
app.include_router(columns.router)
app.include_router(glossary.router)
app.include_router(ingest.router)
app.include_router(lineage.router)
app.include_router(search.router)
app.include_router(security_module.router)
app.include_router(classification.router)

@app.get("/")
async def root():
    return {"service": "cdgc-lite", "version": 1}

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/readyz")
async def readyz():
    # Minimal readiness: verify required env vars exist
    required = [
        "DATABASE_URL",
        "OIDC_ISSUER",
        "OIDC_AUDIENCE",
        "SECRET_KEY",
    ]
    missing = [k for k in required if not os.getenv(k)]
    status = "ready" if not missing else "not-ready"
    return JSONResponse({"status": status, "missing": missing}, status_code=200 if not missing else 503)


@app.get("/metrics")
async def metrics():
    # Use default registry
    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)
