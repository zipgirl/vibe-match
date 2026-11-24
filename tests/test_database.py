from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.app.catalog.database import connect


def test_connect_allows_cross_thread_use_when_requested(tmp_path: Path) -> None:
    connection = connect(tmp_path / "cross-thread.sqlite", check_same_thread=False)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(lambda: connection.execute("SELECT 1").fetchone()[0]).result()
    finally:
        connection.close()
    assert result == 1
