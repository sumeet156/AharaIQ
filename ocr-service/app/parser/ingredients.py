import re

from .models import Ingredient


def _split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(value):
        if character in "([":
            depth += 1
        elif character in ")]":
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def extract_ingredients(text: str) -> list[Ingredient]:
    match = re.search(
        r"\bingredients?\s*:\s*(.+?)(?=\s*\.?\s*(?:\bcontains\b|\bmay\s+contain\b|\ballergen[s]?\b)|$)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return []
    ingredients: list[Ingredient] = []
    for order, original in enumerate(_split_top_level(match.group(1)), start=1):
        normalized = re.sub(r"\s+", " ", original).strip(" .;")
        if normalized:
            ingredients.append(
                Ingredient(originalText=original, normalizedName=normalized.lower(), order=order)
            )
    return ingredients
