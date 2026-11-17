import re

from .models import NutritionFact

FIELD_PATTERNS: list[tuple[str, str, str]] = [
    ("energy", "Energy", r"(?:energy|calories?|kcal)"),
    ("protein", "Protein", r"protein"),
    ("carbohydrates", "Carbohydrates", r"(?:total\s+)?carbohydrates?"),
    ("added_sugars", "Added sugars", r"added\s+sugars?"),
    ("saturated_fat", "Saturated fat", r"saturated\s+(?:fats?|fatty\s+acids?)"),
    ("trans_fat", "Trans fat", r"trans\s+(?:fats?|fatty\s+acids?)"),
    ("dietary_fibre", "Dietary fibre", r"(?:dietary\s+)?fib(?:re|er)"),
    ("total_sugars", "Total sugars", r"total\s+sugars?"),
    ("total_fat", "Total fat", r"total\s+fats?"),
    ("sodium", "Sodium", r"sodium"),
    ("salt", "Salt", r"salt"),
]

NUMBER = r"(?P<number>\d+(?:[.,]\d+)?)"
UNIT = r"(?P<unit>kcal|kj|g|mg|ml|µg|ug|mcg)\b"
BASIS_PATTERN = re.compile(
    r"\b(per\s+(?:100\s*g|100\s*ml|serving|serve|portion))\b", re.IGNORECASE
)


def _basis(text: str) -> str | None:
    match = BASIS_PATTERN.search(text)
    if not match:
        return None
    value = re.sub(r"\s+", "_", match.group(1).lower())
    return value.replace("per_100_g", "per_100_g").replace("per_100_ml", "per_100_ml")


def _normalized(value: float, unit: str) -> tuple[float, str]:
    lower = unit.lower()
    if lower in {"mg", "µg", "ug", "mcg"}:
        return (value / 1000 if lower == "mg" else value / 1_000_000), "g"
    if lower == "kj":
        return value, "kJ"
    if lower == "kcal":
        return value, "kcal"
    return value, lower


def parse_nutrition(text: str) -> list[NutritionFact]:
    facts: list[NutritionFact] = []
    basis = _basis(text)
    for field, label, pattern in FIELD_PATTERNS:
        expression = re.compile(
            rf"(?<!\w)(?P<label>{pattern})(?!\w)\s*[:\-]?\s*(?:\([^)]+\)\s*)?"
            rf"{NUMBER}\s*{UNIT}",
            re.IGNORECASE,
        )
        matches = list(expression.finditer(text))
        if not matches:
            continue
        duplicate_match = len(matches) > 1
        for match in matches:
            raw_number = match.group("number")
            value = float(raw_number.replace(",", "."))
            original = match.group(0).strip()
            normalized_value, normalized_unit = _normalized(value, match.group("unit"))
            review_required = duplicate_match or ("," in raw_number and "." in raw_number)
            facts.append(
                NutritionFact(
                    field=field,
                    label=label,
                    originalValue=original,
                    value=value,
                    normalizedValue=round(normalized_value, 6),
                    unit=match.group("unit").lower(),
                    basis=basis,
                    confidence="review" if review_required else "high",
                    reviewRequired=review_required,
                )
            )
    return facts
