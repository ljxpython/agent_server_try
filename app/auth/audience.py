from __future__ import annotations

from typing import Any


def audience_matches(payload: dict[str, Any], expected_audience: str) -> bool:
    aud_claim = payload.get("aud")
    if isinstance(aud_claim, str) and aud_claim == expected_audience:
        return True

    if isinstance(aud_claim, list):
        for item in aud_claim:
            if isinstance(item, str) and item == expected_audience:
                return True

    azp_claim = payload.get("azp")
    if isinstance(azp_claim, str) and azp_claim == expected_audience:
        return True

    return False
