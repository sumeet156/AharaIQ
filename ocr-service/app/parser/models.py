from typing import Literal

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    rawText: str = Field(min_length=1, max_length=50_000)
    source: Literal["ocr", "reviewed"] = "reviewed"


class NutritionFact(BaseModel):
    field: str
    label: str
    originalValue: str
    value: float
    normalizedValue: float
    unit: str
    basis: str | None
    confidence: Literal["high", "medium", "review"]
    reviewRequired: bool


class Ingredient(BaseModel):
    originalText: str
    normalizedName: str
    order: int
    source: Literal["extracted"] = "extracted"


class Additive(BaseModel):
    originalText: str
    code: str
    name: str | None
    category: str | None
    matchStatus: Literal["known", "unknown"]


class AllergenFinding(BaseModel):
    name: str
    originalText: str
    source: Literal["explicit_declaration", "ingredient_match", "precautionary"]


class ParseResponse(BaseModel):
    rawText: str
    source: Literal["ocr", "reviewed"]
    nutritionFacts: list[NutritionFact]
    ingredients: list[Ingredient]
    additives: list[Additive]
    declaredAllergens: list[AllergenFinding]
    possibleIngredientAllergens: list[AllergenFinding]
    precautionaryStatements: list[AllergenFinding]
    missingFields: list[str]
    reviewWarnings: list[str]
    parsingStatus: Literal["complete", "partial", "needs_review", "empty"]
