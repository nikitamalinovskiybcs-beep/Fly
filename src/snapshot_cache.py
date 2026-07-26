"""Local ready-result cache for fast Streamlit wakeups and reruns."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
import pickle
import threading
import time


SNAPSHOT_PATH = Path("data/runtime/full_analysis_snapshot.pkl")
SNAPSHOT_TTL_SECONDS = 300
MAX_STALE_SECONDS = 86_400
_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_LOCK = threading.Lock()
_REFRESH: Optional[Future] = None
_SCHEDULER_THREAD: Optional[threading.Thread] = None


@dataclass(frozen=True)
class Snapshot:
    payload: Dict[str, object]
    age_seconds: float
    fresh: bool


def _path_for(path: Optional[Path]) -> Path:
    return path or SNAPSHOT_PATH


def load_snapshot(
    tickers: List[str],
    path: Optional[Path] = None,
) -> Optional[Snapshot]:
    """Load a recent snapshot for the exact requested basket."""
    snapshot_path = _path_for(path)
    if not snapshot_path.exists():
        return None
    try:
        with snapshot_path.open("rb") as handle:
            record = pickle.load(handle)
    except (OSError, EOFError, pickle.PickleError):
        return None
    if not isinstance(record, dict):
        return None
    if record.get("tickers") != list(dict.fromkeys(tickers)):
        return None
    created_at = float(record.get("created_at", 0.0))
    age_seconds = max(0.0, time.time() - created_at)
    if age_seconds > MAX_STALE_SECONDS:
        return None
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    return Snapshot(
        payload=payload,
        age_seconds=age_seconds,
        fresh=age_seconds <= SNAPSHOT_TTL_SECONDS,
    )


def save_snapshot(
    tickers: List[str],
    payload: Dict[str, object],
    path: Optional[Path] = None,
) -> None:
    """Atomically persist a completed pipeline result."""
    snapshot_path = _path_for(path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = snapshot_path.with_suffix(".tmp")
    record = {
        "tickers": list(dict.fromkeys(tickers)),
        "created_at": time.time(),
        "created_iso": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    with temporary_path.open("wb") as handle:
        pickle.dump(record, handle, protocol=pickle.HIGHEST_PROTOCOL)
    temporary_path.replace(snapshot_path)


def refresh_in_background(
    tickers: List[str],
    compute: Callable[[List[str]], Dict[str, object]],
) -> bool:
    """Start one stale-snapshot refresh and avoid duplicate workers."""
    global _REFRESH
    with _LOCK:
        if _REFRESH is not None and not _REFRESH.done():
            return False

        def refresh() -> None:
            payload = compute(tickers)
            save_snapshot(tickers, payload)

        _REFRESH = _EXECUTOR.submit(refresh)
        return True


def start_periodic_refresh(
    tickers: List[str],
    compute: Callable[[List[str]], Dict[str, object]],
    interval_seconds: int = 900,
) -> bool:
    """Keep the requested basket warm while the app process is alive."""
    global _SCHEDULER_THREAD
    with _LOCK:
        if _SCHEDULER_THREAD is not None and _SCHEDULER_THREAD.is_alive():
            return False

        def loop() -> None:
            while True:
                time.sleep(interval_seconds)
                refresh_in_background(tickers, compute)

        _SCHEDULER_THREAD = threading.Thread(
            target=loop,
            name="snapshot-refresh",
            daemon=True,
        )
        _SCHEDULER_THREAD.start()
        return True
