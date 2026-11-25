from app.parser.parser import parse_label
from app.parser.table import (
    TableWord,
    extract_table_nutrition,
    group_words_into_rows,
)


def word(text: str, left: int, top: int, confidence: float = 90.0) -> TableWord:
    return TableWord(text, confidence, left, top, max(8, len(text) * 8), 20)


def evidence(*rows: list[TableWord]) -> dict:
    return {
        "lines": [
            {
                "text": " ".join(item.text for item in row),
                "words": [
                    {
                        "text": item.text,
                        "confidence": item.confidence,
                        "left": item.left,
                        "top": item.top,
                        "width": item.width,
                        "height": item.height,
                    }
                    for item in row
                ],
            }
            for row in rows
        ]
    }


def test_groups_words_by_adaptive_vertical_tolerance() -> None:
    rows = group_words_into_rows(
        [
            word("Protein", 10, 100),
            word("10", 200, 104),
            word("g", 225, 103),
            word("Sodium", 10, 140),
            word("643", 200, 145),
            word("mg", 235, 143),
        ],
        image_height=500,
    )

    assert [row.text for row in rows] == ["Protein 10 g", "Sodium 643 mg"]


def test_extracts_explicit_columns_and_multiple_units() -> None:
    result = extract_table_nutrition(
        evidence(
            [word("Nutrients", 10, 10), word("Per", 180, 10), word("100", 220, 10), word("g", 250, 10), word("Per", 330, 10), word("Serving", 365, 10), word("%RDA", 500, 10)],
            [word("Protein", 10, 50), word("10", 220, 50), word("g", 250, 50), word("6.7", 365, 50), word("g", 405, 50), word("5", 500, 50), word("%", 515, 50)],
            [word("Sodium", 10, 90), word("643", 220, 90), word("mg", 255, 90), word("120", 365, 90), word("mg", 405, 90), word("6", 500, 90), word("%", 515, 90)],
        )
    )

    assert result.detected is True
    protein = next(fact for fact in result.facts if fact.field == "protein")
    assert [value.basis for value in protein.values] == ["per_100_g", "per_serving", None]
    assert protein.values[0].unit == "g"
    assert protein.values[1].unit == "g"
    assert protein.values[2].column_type == "rda_percent"


def test_missing_headers_use_spatial_columns_without_guessing_basis() -> None:
    result = extract_table_nutrition(
        evidence(
            [word("Protein", 10, 20), word("10", 220, 20), word("g", 250, 20)],
            [word("Sodium", 10, 60), word("643", 220, 60), word("mg", 250, 60)],
            [word("Fat", 10, 100), word("33.1", 220, 100), word("g", 250, 100)],
        )
    )

    assert result.detected is True
    assert all(fact.values[0].basis is None for fact in result.facts)
    assert all(fact.values[0].review_required for fact in result.facts)


def test_preserves_or_values_and_marks_unassociated_values_for_review() -> None:
    result = extract_table_nutrition(
        evidence(
            [word("Saturated", 10, 20), word("Fat", 85, 20), word("14.9", 220, 20), word("g", 260, 20), word("OR", 310, 20), word("7.6", 350, 20), word("g", 390, 20)],
            [word("Protein", 10, 60), word("10", 220, 60), word("g", 250, 60)],
        )
    )

    fact = next(fact for fact in result.facts if fact.field == "saturated_fat")
    assert len(fact.values) == 2
    assert [value.original_text for value in fact.values] == ["14.9 g", "7.6 g"]
    assert fact.review_required is True


def test_duplicate_rows_are_retained_and_marked() -> None:
    result = extract_table_nutrition(
        evidence(
            [word("Total", 10, 20), word("Fat", 60, 20), word("33.1", 220, 20), word("g", 260, 20)],
            [word("Total", 10, 60), word("Fat", 60, 60), word("34", 220, 60), word("g", 250, 60)],
        )
    )

    assert len(result.facts) == 2
    assert all(fact.review_required for fact in result.facts)
    assert all("Duplicate nutrient row detected." in fact.ambiguity_warnings for fact in result.facts)


def test_non_table_text_uses_existing_parser_fallback() -> None:
    result = parse_label("Protein 10 g")

    assert result.nutritionFacts[0].field == "protein"
    assert result.nutritionFacts[0].basis is None


def test_nutrient_labels_without_numeric_rows_do_not_trigger_table_mode() -> None:
    result = extract_table_nutrition(
        evidence(
            [word("Protein", 10, 20)],
            [word("Sodium", 10, 60)],
            [word("Saturated", 10, 100), word("Fat", 80, 100)],
        )
    )

    assert result.detected is False
    assert result.facts == ()


def test_table_evidence_is_integrated_without_breaking_response_shape() -> None:
    result = parse_label(
        "Protein 10 g Sodium 643 mg",
        source="ocr",
        ocr_evidence=evidence(
            [word("Nutrients", 10, 10), word("Per", 180, 10), word("100", 220, 10), word("g", 250, 10)],
            [word("Protein", 10, 50), word("10", 220, 50), word("g", 250, 50)],
            [word("Sodium", 10, 90), word("643", 220, 90), word("mg", 250, 90)],
        ),
    )
    fields = {fact.field: fact for fact in result.nutritionFacts}

    assert result.source == "ocr"
    assert fields["protein"].basis == "per_100_g"
    assert fields["sodium"].normalizedValue == 0.643
    assert fields["protein"].sourceCoordinates is not None
