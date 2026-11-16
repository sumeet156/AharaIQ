from fastapi.testclient import TestClient

from app.main import app
from app.parser.parser import parse_label

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
