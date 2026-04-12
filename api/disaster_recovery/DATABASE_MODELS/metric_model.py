"""
Metric Model — SQLAlchemy model for time-series performance metrics.
Stores system, database, and application metrics for trending,
alerting, and capacity planning.
"""
from sqlalchemy import Column, String, Float, DateTime, JSON, Index
from datetime import datetime
import uuid
from ..sa_models import Base


class Metric(Base):
    """
    Generic metric data point. Compatible with Prometheus-style metrics.
    Indexed for efficient time-range queries.
    """
    __tablename__ = "metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    metric_name = Column(String(200), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50))           # percent, seconds, bytes, count
    component = Column(String(200))     # which system component
    labels = Column(JSON, default=dict) # {"host": "db-01", "region": "us-east-1"}

    __table_args__ = (
        Index("ix_metrics_name_time", "metric_name", "timestamp"),
        Index("ix_metrics_component_time", "component", "timestamp"),
    )

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


class MetricRepository:
    """Helper repository for time-series metric queries."""
    def __init__(self, db_session):
        self.db = db_session

    def record(self, metric_name: str, value: float, component: str = None,
               unit: str = None, labels: dict = None):
        m = Metric(metric_name=metric_name, value=value, component=component,
                   unit=unit, labels=labels or {})
        self.db.add(m)
        self.db.commit()
        return m

    def query_range(self, metric_name: str, from_dt: datetime, to_dt: datetime) -> list:
        return self.db.query(Metric).filter(
            Metric.metric_name == metric_name,
            Metric.timestamp.between(from_dt, to_dt)
        ).order_by(Metric.timestamp).all()

    def latest(self, metric_name: str, component: str = None):
        q = self.db.query(Metric).filter(Metric.metric_name == metric_name)
        if component:
            q = q.filter(Metric.component == component)
        return q.order_by(Metric.timestamp.desc()).first()


__all__ = ["Metric", "MetricRepository"]
