from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class DiscoverResult:
    assets: list[Dict[str, Any]]
    columns: list[Dict[str, Any]]


@dataclass
class HarvestResult:
    payload: Dict[str, Any]
    last_seen_at: Optional[datetime]


class Connector:
    def discover(self, last_seen_at: Optional[datetime] = None) -> DiscoverResult:
        raise NotImplementedError

    def harvest(self, since: Optional[datetime] = None) -> HarvestResult:
        raise NotImplementedError


def get_connector(source: str) -> Connector:
    source = (source or "").lower()
    if source == "snowflake":
        from .snowflake.impl import SnowflakeConnector
        return SnowflakeConnector()
    if source == "postgres":
        from .postgres.impl import PostgresConnector
        return PostgresConnector()
    if source == "s3":
        from .s3.impl import S3Connector
        return S3Connector()
    raise ValueError(f"Unknown connector source: {source}")
