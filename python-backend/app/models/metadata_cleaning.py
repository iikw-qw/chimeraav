from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from ._common import new_uuid, utc_now


class MetadataCleaning(Base):
    __tablename__ = "metadata_cleanings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    file_path: Mapped[str] = mapped_column(String(1024))
    original_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cleaned_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exif_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    gps_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    digital_fingerprint_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    cleaned_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
