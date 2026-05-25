import os

from fastapi import FastAPI, Response

from database.db import init_database
from database.monitoring_repository import get_monitoring_stats


app = FastAPI(
    title="SPIKA Monitoring API",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    init_database()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "spika-monitoring",
        "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "local"),
    }


@app.get("/admin-stats")
def admin_stats():
    return get_monitoring_stats()


@app.get("/metrics")
def metrics():
    stats = get_monitoring_stats()

    lines = []

    for key, value in stats.items():
        metric_name = f"spika_{key}"

        lines.append(f"# HELP {metric_name} SPIKA metric: {key}")
        lines.append(f"# TYPE {metric_name} gauge")
        lines.append(f"{metric_name} {float(value)}")

    body = "\n".join(lines) + "\n"

    return Response(
        content=body,
        media_type="text/plain; version=0.0.4",
    )