from __future__ import annotations

import logging

from fastapi import Request


logger = logging.getLogger("proxy.platform")


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")
