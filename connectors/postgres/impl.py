from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..base import Connector, DiscoverResult, HarvestResult


class PostgresConnector(Connector):
    def discover(self, last_seen_at: Optional[datetime] = None) -> DiscoverResult:
        return DiscoverResult(
            assets=[{"system": "postgres", "name": "public.table"}],
            columns=[{"asset": "public.table", "name": "id", "data_type": "INTEGER"}],
        )

    def harvest(self, since: Optional[datetime] = None) -> HarvestResult:
        payload: Dict[str, Any] = {
            "type": "postgres",
            "harvested_at": datetime.utcnow().isoformat() + "Z",
            "since": since.isoformat() + "Z" if since else None,
            "items": [
                {"asset": "public.table", "row_count": 123},
            ],
        }
        return HarvestResult(payload=payload, last_seen_at=datetime.utcnow())
