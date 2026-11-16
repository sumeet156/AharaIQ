import json
import re
from pathlib import Path

from .models import Additive

DATASET = json.loads(
    (Path(__file__).parent.parent / "data" / "additives.json").read_text(encoding="utf-8")
)
INS_PATTERN = re.compile(r"\b(?:INS|E)\s*[-:]?\s*(\d{3})(?:\s*(\([ivx]+\)))?\b", re.IGNORECASE)


def detect_additives(text: str) -> list[Additive]:
    findings: list[Additive] = []
    seen: set[str] = set()
    for match in INS_PATTERN.finditer(text):
        suffix = (match.group(2) or "").lower()
        code = f"{match.group(1)}{suffix}"
        if code in seen:
            continue
        entry = DATASET.get(code)
        findings.append(
            Additive(
                originalText=match.group(0),
                code=code,
                name=entry.get("name") if entry else None,
                category=entry.get("category") if entry else None,
                matchStatus="known" if entry else "unknown",
            )
        )
        seen.add(code)
    return findings
