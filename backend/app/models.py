from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|completed|failed
    progress: Mapped[int] = mapped_column(Integer, default=0)  # current generation index
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full result JSON — populated progressively as generations complete
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Quick-access denormalised stats
    final_drift_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_diversity: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_drift_events: Mapped[int | None] = mapped_column(Integer, nullable=True)
