from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..base import Connector, DiscoverResult, HarvestResult


class S3Connector(Connector):
    def discover(self, last_seen_at: Optional[datetime] = None) -> DiscoverResult:
        return DiscoverResult(
            assets=[{"system": "s3", "name": "s3://bucket/prefix/"}],
            columns=[],
        )

    def harvest(self, since: Optional[datetime] = None) -> HarvestResult:
        payload: Dict[str, Any] = {
            "type": "s3",
            "harvested_at": datetime.utcnow().isoformat() + "Z",
            "since": since.isoformat() + "Z" if since else None,
            "items": [
                {"asset": "s3://bucket/prefix/", "objects": 3},
            ],
        }
        return HarvestResult(payload=payload, last_seen_at=datetime.utcnow())
