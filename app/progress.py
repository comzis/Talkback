"""Pure progress math for document ingestion."""


def ingest_metrics(done: int, total: int, elapsed_seconds: float) -> dict:
    """Return chunk progress, speed, and remaining seconds for the status API."""
    speed = (done / elapsed_seconds) if elapsed_seconds > 0 and done else 0.0
    remaining_chunks = max(total - done, 0)
    remaining = (remaining_chunks / speed) if speed > 0 else 0
    percent = int((done / total) * 100) if total else 0
    return {
        "current": done,
        "total": total,
        "chunks_per_second": round(speed, 2),
        "estimated_time_remaining": int(remaining),
        "progress": min(percent, 100),
    }
