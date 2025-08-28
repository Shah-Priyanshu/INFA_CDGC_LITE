from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class SystemBase(BaseModel):
    name: str
    description: str | None = None
    visibility: str | None = None


class SystemCreate(SystemBase):
    pass


class SystemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None


class SystemOut(SystemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Asset schemas
class AssetBase(BaseModel):
    system_id: int
    name: str
    description: str | None = None
    visibility: str | None = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None


class AssetOut(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime
    column_names: str | None = None

    class Config:
        from_attributes = True


class AssetSearchOut(AssetOut):
    highlight: str | None = None


# Column schemas
class ColumnBase(BaseModel):
    asset_id: int
    name: str
    data_type: str | None = None
    description: str | None = None


class ColumnCreate(ColumnBase):
    pass


class ColumnUpdate(BaseModel):
    name: str | None = None
    data_type: str | None = None
    description: str | None = None


class ColumnOut(ColumnBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ColumnSearchOut(ColumnOut):
    highlight: str | None = None
