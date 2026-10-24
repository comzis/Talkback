"""
LangChain / LangSmith monitoring helpers.

This module provides a thin abstraction around the LangSmith client so that
FastAPI endpoints can log ingest/query runs without taking a hard dependency
on LangSmith being configured at runtime.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from langsmith import Client
except ImportError:  # pragma: no cover - langsmith optional at runtime
    Client = None  # type: ignore


logger = logging.getLogger(__name__)


class LangChainMonitor:
    """Small helper that sends events to LangChain/LangSmith when enabled."""

    def __init__(self) -> None:
        self.enabled = os.getenv("LANGCHAIN_MONITORING", "false").lower() in {"1", "true", "yes"}
        self.project_name = os.getenv("LANGCHAIN_PROJECT", "Talkback")
        self.client: Optional[Client] = None

        if not self.enabled:
            logger.info("LangChain monitoring disabled (set LANGCHAIN_MONITORING=true to enable).")
            return

        if Client is None:
            logger.warning(
                "LangChain monitoring enabled but 'langsmith' is not installed. "
                "Install it or disable monitoring."
            )
            self.enabled = False
            return

        try:
            self.client = Client()
            logger.info("LangChain monitor initialized for project '%s'.", self.project_name)
        except Exception as exc:  # pragma: no cover - depends on env at runtime
            logger.warning("Unable to initialize LangChain monitor: %s", exc)
            self.enabled = False

    def start_run(
        self,
        name: str,
        run_type: str,
        inputs: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a LangSmith run and return the run id."""
        if not self.enabled or self.client is None:
            return None

        run_id = str(uuid.uuid4())
        try:
            self.client.create_run(
                name=name,
                run_type=run_type,
                inputs=inputs or {},
                id=run_id,
                project_name=self.project_name,
                tags=tags or [],
                metadata=metadata or {},
                start_time=datetime.now(timezone.utc),
            )
            return run_id
        except Exception as exc:  # pragma: no cover - depends on external service
            logger.warning("LangChain monitor failed to create run '%s': %s", name, exc)
            return None

    def end_run(
        self,
        run_id: Optional[str],
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Finalize a LangSmith run."""
        if not run_id or not self.client or not self.enabled:
            return

        try:
            self.client.update_run(
                run_id,
                outputs=outputs or {},
                error=error,
                metadata=metadata or {},
                end_time=datetime.now(timezone.utc),
            )
        except Exception as exc:  # pragma: no cover - depends on external service
            logger.warning("LangChain monitor failed to update run '%s': %s", run_id, exc)

    def log_event(
        self,
        name: str,
        run_type: str,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Fire-and-forget convenience wrapper."""
        run_id = self.start_run(name, run_type, inputs, tags, metadata)
        self.end_run(run_id, outputs, error, metadata)

