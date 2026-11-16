import re

from .models import AllergenFinding

ALLERGENS = {
    "milk": r"\bmilk\b|\bdairy\b",
    "soy": r"\bsoy(?:a)?\b",
    "wheat": r"\bwheat\b",
    "gluten": r"\bgluten\b",
    "peanuts": r"\bpeanuts?\b",
    "tree nuts": r"\btree\s+nuts?\b|\balmonds?\b|\bcashews?\b|\bwalnuts?\b",
    "sesame": r"\bsesame\b",
}


def _find(text: str, source: str) -> list[AllergenFinding]:
    findings: list[AllergenFinding] = []
    seen: set[str] = set()
    for name, pattern in ALLERGENS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match and name not in seen:
            findings.append(
                AllergenFinding(name=name, originalText=match.group(0), source=source)
            )
            seen.add(name)
    return findings


def detect_allergens(text: str, ingredient_text: str) -> tuple[
    list[AllergenFinding], list[AllergenFinding], list[AllergenFinding]
]:
    explicit_match = re.search(
        r"\b(?:contains|allergens?)\s*:?\s*(.+?)(?=\bmay\s+contain\b|$)",
        text,
        re.IGNORECASE,
    )
    precautionary_match = re.search(r"\bmay\s+contain\s+(.+)", text, re.IGNORECASE)
    declared = _find(explicit_match.group(1), "explicit_declaration") if explicit_match else []
    precautionary = (
        _find(precautionary_match.group(1), "precautionary")
        if precautionary_match
        else []
    )
    possible = _find(ingredient_text, "ingredient_match")
    declared_names = {finding.name for finding in declared}
    possible = [finding for finding in possible if finding.name not in declared_names]
    return declared, possible, precautionary
