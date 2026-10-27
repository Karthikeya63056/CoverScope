"""MongoDB healthcheck utility and diagnostic runner for CoverScope.

Verifies live database connectivity using an active admin ping command without
revealing credentials, server topology, or passwords in output or exceptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import sys
import time

from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from backend.config import settings
from backend.database.client import (
    close_mongodb_client,
    get_mongodb_client,
    redact_mongo_uri,
    sanitize_mongo_error,
)


class DatabaseHealthStatus(str, Enum):
    """Categorized health outcomes for the MongoDB Atlas integration."""
    NOT_CONFIGURED = "not_configured"
    CONNECTED = "connected"
    CONNECTION_FAILED = "connection_failed"
    AUTH_FAILED = "auth_failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DatabaseHealthReport:
    """Structured report returned by check_mongodb_health."""
    status: DatabaseHealthStatus
    database_name: str
    message: str
    latency_ms: float = 0.0
    redacted_uri: str = "<not configured>"

    @property
    def is_connected(self) -> bool:
        return self.status == DatabaseHealthStatus.CONNECTED


def check_mongodb_health(uri: str | None = None) -> DatabaseHealthReport:
    """Execute a live MongoDB ping to verify database connectivity.

    Never exposes passwords, secrets, or internal server paths.
    """
    target_uri = uri if uri is not None else os.getenv("MONGODB_URI")
    db_name = (settings.mongodb_database or "coverscope").strip()
    masked = redact_mongo_uri(target_uri)

    if not target_uri or not target_uri.strip():
        return DatabaseHealthReport(
            status=DatabaseHealthStatus.NOT_CONFIGURED,
            database_name=db_name,
            message="MongoDB URI is not configured. Running in offline in-memory session mode.",
            latency_ms=0.0,
            redacted_uri=masked,
        )

    t0 = time.perf_counter()
    try:
        # Reuse the singleton and validate it with a real ping. Forcing a new
        # pool on every health request would churn connections under load.
        client = get_mongodb_client(target_uri)
        if client is None:
            return DatabaseHealthReport(
                status=DatabaseHealthStatus.NOT_CONFIGURED,
                database_name=db_name,
                message="MongoDB client could not be initialized (empty URI).",
                latency_ms=0.0,
                redacted_uri=masked,
            )

        # Real ping command against the cluster
        client.admin.command("ping")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return DatabaseHealthReport(
            status=DatabaseHealthStatus.CONNECTED,
            database_name=db_name,
            message=f"Connected successfully to MongoDB Atlas database '{db_name}'.",
            latency_ms=round(elapsed_ms, 2),
            redacted_uri=masked,
        )

    except OperationFailure as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        # Authentication failure or permission denied
        return DatabaseHealthReport(
            status=DatabaseHealthStatus.AUTH_FAILED,
            database_name=db_name,
            message=f"Authentication or authorization failed: {sanitize_mongo_error(exc)}",
            latency_ms=round(elapsed_ms, 2),
            redacted_uri=masked,
        )

    except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return DatabaseHealthReport(
            status=DatabaseHealthStatus.UNAVAILABLE,
            database_name=db_name,
            message=f"Database cluster unreachable (timeout): {sanitize_mongo_error(exc)}",
            latency_ms=round(elapsed_ms, 2),
            redacted_uri=masked,
        )

    except ConfigurationError as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return DatabaseHealthReport(
            status=DatabaseHealthStatus.CONNECTION_FAILED,
            database_name=db_name,
            message=f"Malformed MongoDB configuration or URI: {sanitize_mongo_error(exc)}",
            latency_ms=round(elapsed_ms, 2),
            redacted_uri=masked,
        )

    except PyMongoError as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return DatabaseHealthReport(
            status=DatabaseHealthStatus.CONNECTION_FAILED,
            database_name=db_name,
            message=f"Connection failed: {sanitize_mongo_error(exc)}",
            latency_ms=round(elapsed_ms, 2),
            redacted_uri=masked,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return DatabaseHealthReport(
            status=DatabaseHealthStatus.CONNECTION_FAILED,
            database_name=db_name,
            message=f"Unexpected error checking MongoDB status: {sanitize_mongo_error(exc)}",
            latency_ms=round(elapsed_ms, 2),
            redacted_uri=masked,
        )


def main() -> int:
    """CLI runner: python -m backend.database.healthcheck"""
    print("=" * 65)
    print("CoverScope MongoDB Atlas Health Check")
    print("=" * 65)

    report = check_mongodb_health()

    print(f"Status:        {report.status.value.upper()}")
    print(f"Target DB:     {report.database_name}")
    print(f"Cluster URI:   {report.redacted_uri}")
    if report.latency_ms > 0:
        print(f"Ping Latency:  {report.latency_ms:.1f} ms")
    print(f"Diagnostic:    {report.message}")
    print("=" * 65)

    if report.status == DatabaseHealthStatus.CONNECTED:
        print("[SUCCESS] MongoDB Atlas connection verified and operational.")
        return 0
    elif report.status == DatabaseHealthStatus.NOT_CONFIGURED:
        print("[NOTICE] Running in safe offline mode. Set MONGODB_URI to enable Atlas persistence.")
        return 0
    else:
        print(f"[FAIL] MongoDB connection verification failed ({report.status.value}).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
