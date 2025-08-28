from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional

from .security import User


def audit_log(action: str, resource: str, resource_id: Any | None, user: Optional[User], extra: dict | None = None) -> None:
    """
    Minimal audit logger: prints structured JSON to stdout. In production, forward to a sink.
    Fields: ts, action, resource, resource_id, user_sub, user_upn, extra.
    Controlled by AUDIT_ENABLED env (defaults to enabled).
    """
    if os.getenv("AUDIT_ENABLED", "1") != "1":
        return
    evt = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "user_sub": getattr(user, "sub", None),
        "user_upn": getattr(user, "upn", None),
        "extra": extra or {},
    }
    try:
        print(json.dumps({"audit": evt}, separators=(",", ":")))
    except Exception:
        # Best-effort; avoid raising from audit path
        pass
