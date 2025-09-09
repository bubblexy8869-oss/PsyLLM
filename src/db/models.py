from __future__ import annotations
import uuid, datetime as dt
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Boolean, JSON, Float, Text, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def _uuid() -> str:
    return uuid.uuid4().hex

class User(Base):
    __tablename__ = "users"
    user_id = Column(String(64), primary_key=True, default=_uuid)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=False, index=True)
    status = Column(String(32), default="active")  # active|paused|completed
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

    user = relationship("User", backref="sessions")

class Message(Base):
    __tablename__ = "messages"
    id = Column(String(64), primary_key=True, default=_uuid)
    session_id = Column(String(64), ForeignKey("sessions.session_id"), index=True, nullable=False)
    role = Column(String(16), nullable=False)  # user|assistant|system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

class Answer(Base):
    __tablename__ = "answers"
    id = Column(String(64), primary_key=True, default=_uuid)
    session_id = Column(String(64), ForeignKey("sessions.session_id"), index=True, nullable=False)
    question_id = Column(String(32), index=True, nullable=False)
    dimension = Column(String(64), index=True, nullable=False)
    question_text = Column(Text, nullable=False)
    user_reply = Column(Text, nullable=False)
    score = Column(Integer, nullable=False)
    weight = Column(Float, default=1.0, nullable=False)
    reverse_scored = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        # 同一 session 的同一题可记录多次（澄清/复测），靠 created_at 取最新；如需“覆盖”，可改为 UniqueConstraint
        None,
    )

class ItemScore(Base):
    __tablename__ = "item_scores"
    id = Column(String(64), primary_key=True, default=_uuid)
    session_id = Column(String(64), ForeignKey("sessions.session_id"), index=True, nullable=False)
    question_id = Column(String(32), index=True, nullable=False)
    dimension = Column(String(64), index=True, nullable=False)
    score = Column(Integer, nullable=False)
    weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    id = Column(String(64), primary_key=True, default=_uuid)
    session_id = Column(String(64), ForeignKey("sessions.session_id"), index=True, nullable=False)
    record = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

class ReportVersion(Base):
    __tablename__ = "report_versions"
    id = Column(String(64), primary_key=True, default=_uuid)
    session_id = Column(String(64), ForeignKey("sessions.session_id"), index=True, nullable=False)
    version_no = Column(Integer, nullable=False)   # 1,2,3...
    profile = Column(JSON, nullable=True)
    dim_scores = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)
    overall_severity = Column(String(32), nullable=True)
    interventions = Column(JSON, nullable=True)
    report_json = Column(JSON, nullable=True)  # 完整报告结构化 JSON
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "version_no", name="uq_report_session_version"),
    )