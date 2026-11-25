from .additives import detect_additives
from .allergens import detect_allergens
from .ingredients import extract_ingredients
from .models import NutritionFact, ParseResponse
from .nutrition import FIELD_PATTERNS, _normalized, parse_nutrition
from .table import TableExtraction, extract_table_nutrition


def _table_facts(extraction: TableExtraction):
    facts: list[NutritionFact] = []
    for row in extraction.facts:
        for value in row.values:
            if value.value is None or value.unit is None:
                continue
            normalized_value, _ = _normalized(value.value, value.unit)
            confidence = "review" if row.review_required or value.review_required else "high"
            facts.append(
                NutritionFact(
                    field=row.field,
                    label=row.label,
                    originalValue=value.original_text,
                    value=value.value,
                    normalizedValue=round(normalized_value, 6),
                    unit=value.unit,
                    basis=value.basis,
                    confidence=confidence,
                    reviewRequired=row.review_required or value.review_required,
                    columnType=value.column_type,
                    ocrConfidence=value.confidence,
                    sourceText=row.source_text,
                    sourceCoordinates=value.source_coordinates,
                    ambiguityWarnings=list(
                        dict.fromkeys(
                            (*row.ambiguity_warnings, *value.ambiguity_warnings)
                        )
                    ),
                )
            )
    return facts


def parse_label(
    raw_text: str,
    source: str = "reviewed",
    ocr_evidence: dict | None = None,
) -> ParseResponse:
    text = " ".join(raw_text.split())
    text_nutrition = parse_nutrition(text)
    table_extraction = extract_table_nutrition(ocr_evidence)
    table_facts = _table_facts(table_extraction)
    table_fields = {fact.field for fact in table_facts}
    nutrition = [
        fact for fact in text_nutrition if fact.field not in table_fields
    ]
    nutrition.extend(table_facts)
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
    if table_extraction.detected:
        warnings.extend(table_extraction.warnings)
        if any(fact.reviewRequired for fact in table_facts):
            warnings.append("One or more table values need manual review.")
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
