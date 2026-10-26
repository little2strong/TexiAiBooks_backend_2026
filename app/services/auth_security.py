"""Shared PostgreSQL rate limits and deliberately minimal security audit events."""

import time

from fastapi import HTTPException, Request
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_secret
from app.models import RateLimitBucket, SecurityEvent


def audit(db: Session, event: str, user_id=None, session_id=None, actor_hash=None):
    db.add(SecurityEvent(event=event, user_id=user_id, session_id=session_id, actor_hash=actor_hash))


def rate_limit(db: Session, settings: Settings, request: Request, action: str,
               target: str = "", target_limit: int = 10, ip_limit: int = 30, window: int = 900):
    """Atomic counters shared by workers. Never trust caller-supplied proxy headers."""
    now = int(time.time())
    start = now // window * window
    peer = request.client.host if request.client else "unknown"
    exceeded = False
    for scope, value, limit in (("ip", peer, ip_limit), ("target", target, target_limit)):
        if scope == "target" and not target:
            continue
        key = hash_secret(f"rate:{action}:{scope}:{value}", settings)
        statement = insert(RateLimitBucket).values(key=key, window_start=start, count=1)
        statement = statement.on_conflict_do_update(
            index_elements=[RateLimitBucket.key],
            set_={"window_start": start, "count": case(
                (RateLimitBucket.window_start == start, RateLimitBucket.count + 1), else_=1)},
        ).returning(RateLimitBucket.count)
        exceeded |= db.scalar(statement) > limit
    if exceeded:
        audit(db, "rate_limit", actor_hash=hash_secret(f"peer:{peer}", settings))
    # Persist failed attempts even if later credential verification raises.
    db.commit()
    if exceeded:
        raise HTTPException(429, "Too many attempts", headers={"Retry-After": str(start + window - now)})
