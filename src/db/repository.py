from __future__ import annotations
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session as SASession
from db.models import User, Session, Message, Answer, ItemScore, ExecutionLog, ReportVersion

class Repo:
    def __init__(self, sa: SASession):
        self.sa = sa

    # --- 用户/会话 ---
    def ensure_user(self, user_id: str) -> User:
        u = self.sa.get(User, user_id)
        if not u:
            u = User(user_id=user_id)
            self.sa.add(u)
        return u

    def ensure_session(self, session_id: str, user_id: str) -> Session:
        s = self.sa.get(Session, session_id)
        if not s:
            s = Session(session_id=session_id, user_id=user_id)
            self.sa.add(s)
        return s

    def update_session_status(self, session_id: str, status: str):
        s = self.sa.get(Session, session_id)
        if s:
            s.status = status

    # --- 消息 & 执行日志 ---
    def append_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        for m in messages:
            self.sa.add(Message(session_id=session_id, role=m["role"], content=m["content"]))

    def append_execution_logs(self, session_id: str, logs: List[Dict[str, Any]]):
        for rec in logs:
            self.sa.add(ExecutionLog(session_id=session_id, record=rec))

    # --- 答案/打分 ---
    def append_answer(self, session_id: str, ans: Dict[str, Any]):
        self.sa.add(Answer(
            session_id=session_id,
            question_id=ans["question_id"],
            dimension=ans["dimension"],
            question_text=ans["text"],
            user_reply=ans["answer"],
            score=ans["score"],
            weight=ans.get("weight", 1.0),
            reverse_scored=bool(ans.get("reverse_scored", False))
        ))

    def append_item_score(self, session_id: str, item: Dict[str, Any]):
        self.sa.add(ItemScore(
            session_id=session_id,
            question_id=item["question_id"],
            dimension=item["dimension"],
            score=item["score"],
            weight=item.get("weight", 1.0),
        ))

    # --- 报告版本 ---
    def next_report_version_no(self, session_id: str) -> int:
        q = self.sa.execute(
            select(func.coalesce(func.max(ReportVersion.version_no), 0)).where(ReportVersion.session_id == session_id)
        ).scalar_one()
        return int(q) + 1

    def create_report_version(self, session_id: str, payload: Dict[str, Any]) -> ReportVersion:
        ver = self.next_report_version_no(session_id)
        rv = ReportVersion(
            session_id=session_id,
            version_no=ver,
            profile=payload.get("profile"),
            dim_scores=payload.get("dim_scores"),
            overall_score=payload.get("overall_score"),
            overall_severity=payload.get("overall_severity"),
            interventions=payload.get("interventions"),
            report_json=payload.get("report"),
        )
        self.sa.add(rv)
        return rv