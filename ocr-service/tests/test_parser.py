from fastapi.testclient import TestClient

from app.main import app
from app.parser.parser import parse_label
from app.parser.nutrition import parse_nutrition

client = TestClient(app)


def test_parses_indian_nutrition_labels_and_basis() -> None:
    result = parse_label(
        "Nutrition Information per 100 g Energy 321.94 kcal Protein 10.59 g "
        "Carbohydrates 64.72 g Total Fat 1.47 g Total Fibre 11.23 g"
    )
    fields = {fact.field: fact for fact in result.nutritionFacts}
    assert fields["energy"].normalizedValue == 321.94
    assert fields["protein"].basis == "per_100_g"
    assert fields["dietary_fibre"].normalizedValue == 11.23
    assert "total_sugars" in result.missingFields


def test_normalizes_milligrams_without_turning_missing_into_zero() -> None:
    result = parse_label("Sodium 450 mg Vitamin A 287 ug")
    fields = {fact.field: fact for fact in result.nutritionFacts}
    assert fields["sodium"].normalizedValue == 0.45
    assert fields["sodium"].unit == "mg"
    assert "protein" in result.missingFields


def test_keeps_total_saturated_and_trans_fat_distinct() -> None:
    facts = parse_nutrition("Total Fat 33 g Saturated Fat 5 g Trans Fat 1 g")

    assert [(fact.field, fact.value) for fact in facts] == [
        ("saturated_fat", 5.0),
        ("trans_fat", 1.0),
        ("total_fat", 33.0),
    ]


def test_does_not_infer_total_fat_from_saturated_or_trans_fat() -> None:
    assert [fact.field for fact in parse_nutrition("Saturated Fat 5 g")] == [
        "saturated_fat"
    ]
    assert [fact.field for fact in parse_nutrition("Trans Fat 1 g")] == [
        "trans_fat"
    ]


def test_keeps_added_and_total_sugars_distinct() -> None:
    facts = parse_nutrition("Added Sugars 2 g Total Sugars 4 g")

    assert [(fact.field, fact.value) for fact in facts] == [
        ("added_sugars", 2.0),
        ("total_sugars", 4.0),
    ]


def test_does_not_infer_total_sugars_from_added_sugars() -> None:
    assert [fact.field for fact in parse_nutrition("Added Sugars 2 g")] == [
        "added_sugars"
    ]


def test_ignores_isolated_noisy_fat_and_sugar_words() -> None:
    facts = parse_nutrition("Ingredients contain fat and sugar; FATS are mentioned.")

    assert facts == []


def test_marks_duplicate_total_fat_values_for_review() -> None:
    facts = parse_nutrition("Total Fat 33 g Total Fat 34 g")

    assert len(facts) == 2
    assert [fact.originalValue for fact in facts] == [
        "Total Fat 33 g",
        "Total Fat 34 g",
    ]
    assert all(fact.reviewRequired for fact in facts)
    assert all(fact.confidence == "review" for fact in facts)


def test_extracts_nested_ingredients_and_additives() -> None:
    result = parse_label(
        "Ingredients: wheat flour, chocolate (sugar, cocoa solids, INS 322), "
        "citric acid INS 330. Contains milk. May contain peanuts."
    )
    assert [item.normalizedName for item in result.ingredients] == [
        "wheat flour",
        "chocolate (sugar, cocoa solids, ins 322)",
        "citric acid ins 330",
    ]
    assert {item.code for item in result.additives} == {"322", "330"}
    assert result.declaredAllergens[0].name == "milk"
    assert result.precautionaryStatements[0].name == "peanuts"
    assert any(item.name == "wheat" for item in result.possibleIngredientAllergens)


def test_unknown_additives_are_not_labelled_harmful() -> None:
    result = parse_label("Ingredients: flour, INS 999")
    assert result.additives[0].matchStatus == "unknown"
    assert result.additives[0].name is None


def test_parse_endpoint_rejects_empty_text_and_returns_structured_data() -> None:
    response = client.post("/parse", json={"rawText": ""})
    assert response.status_code == 422

    response = client.post(
        "/parse",
        json={"rawText": "Protein 5 g", "source": "reviewed"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rawText"] == "Protein 5 g"
    assert body["source"] == "reviewed"
    assert body["nutritionFacts"][0]["field"] == "protein"


def test_parse_endpoint_uses_optional_ocr_evidence_when_available() -> None:
    evidence = {
        "lines": [
            {
                "text": "Nutrients Per 100 g",
                "words": [
                    {"text": "Nutrients", "confidence": 95, "left": 10, "top": 10, "width": 70, "height": 20},
                    {"text": "Per", "confidence": 95, "left": 180, "top": 10, "width": 24, "height": 20},
                    {"text": "100", "confidence": 95, "left": 220, "top": 10, "width": 30, "height": 20},
                    {"text": "g", "confidence": 95, "left": 255, "top": 10, "width": 10, "height": 20},
                ],
            },
            {
                "text": "Protein 10 g",
                "words": [
                    {"text": "Protein", "confidence": 95, "left": 10, "top": 50, "width": 60, "height": 20},
                    {"text": "10", "confidence": 95, "left": 220, "top": 50, "width": 20, "height": 20},
                    {"text": "g", "confidence": 95, "left": 250, "top": 50, "width": 10, "height": 20},
                ],
            },
            {
                "text": "Sodium 643 mg",
                "words": [
                    {"text": "Sodium", "confidence": 95, "left": 10, "top": 90, "width": 60, "height": 20},
                    {"text": "643", "confidence": 95, "left": 220, "top": 90, "width": 30, "height": 20},
                    {"text": "mg", "confidence": 95, "left": 255, "top": 90, "width": 20, "height": 20},
                ],
            },
        ]
    }

    response = client.post(
        "/parse",
        json={
            "rawText": "Protein 10 g Sodium 643 mg",
            "source": "ocr",
            "ocrEvidence": evidence,
        },
    )

    assert response.status_code == 200
    fields = {fact["field"]: fact for fact in response.json()["nutritionFacts"]}
    assert fields["protein"]["basis"] == "per_100_g"
    assert fields["sodium"]["sourceCoordinates"] is not None
