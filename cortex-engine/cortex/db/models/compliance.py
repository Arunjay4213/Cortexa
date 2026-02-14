"""ComplianceCertificate model for GDPR deletion audit trail.

See PROVENANCE.md Section 7 for the certificate schema.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cortex.db.models.base import Base

try:
    from uuid_utils import uuid7 as _uuid7
except ImportError:
    from uuid import uuid4 as _uuid7


def _generate_uuid() -> UUID:
    return _uuid7()


class RequestType(str, enum.Enum):
    """See PROVENANCE.md Section 7."""

    gdpr_deletion = "gdpr_deletion"
    audit_request = "audit_request"
    data_export = "data_export"


class ComplianceCertificate(Base):
    """Cryptographic audit log for GDPR deletion operations.

    See PROVENANCE.md Section 7.
    """

    __tablename__ = "compliance_certificates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    request_type: Mapped[RequestType] = mapped_column(
        Enum(RequestType, name="request_type_enum", create_constraint=False),
        nullable=False,
    )
    footprint_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    nodes_deleted: Mapped[int] = mapped_column(Integer, nullable=False)
    edges_affected: Mapped[int] = mapped_column(Integer, nullable=False)
    deletion_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    grace_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    hard_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    certificate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
