from .additives import detect_additives
from .allergens import detect_allergens
from .ingredients import extract_ingredients
from .models import ParseResponse
from .nutrition import FIELD_PATTERNS, parse_nutrition


def parse_label(raw_text: str, source: str = "reviewed") -> ParseResponse:
    text = " ".join(raw_text.split())
    nutrition = parse_nutrition(text)
    ingredients = extract_ingredients(text)
    ingredient_text = ", ".join(item.originalText for item in ingredients)
    additives = detect_additives(text)
    declared, possible, precautionary = detect_allergens(text, ingredient_text)
    present_fields = {fact.field for fact in nutrition}
    missing = [field for field, _, _ in FIELD_PATTERNS if field not in present_fields]
    warnings: list[str] = []
    if not text:
        warnings.append("No readable text was provided.")
    if not nutrition:
        warnings.append("No nutrition facts were confidently identified.")
    if text and not ingredients:
        warnings.append("No ingredients section was identified.")
    if any(fact.reviewRequired for fact in nutrition):
        warnings.append("One or more numeric values need manual review.")
    status = "empty" if not text else "complete" if not missing and not warnings else "partial"
    if any(fact.reviewRequired for fact in nutrition):
        status = "needs_review"
    return ParseResponse(
        rawText=raw_text,
        source=source,
        nutritionFacts=nutrition,
        ingredients=ingredients,
        additives=additives,
        declaredAllergens=declared,
        possibleIngredientAllergens=possible,
        precautionaryStatements=precautionary,
        missingFields=missing,
        reviewWarnings=warnings,
        parsingStatus=status,
    )
