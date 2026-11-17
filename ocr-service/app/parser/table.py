from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median
from typing import Any


NUTRIENT_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("energy", "Energy", r"energy|calories?|kcal"),
    ("protein", "Protein", r"protein"),
    ("carbohydrates", "Carbohydrates", r"carbohydrates?|carbs?"),
    ("added_sugars", "Added sugars", r"added\s+sugars?"),
    ("total_sugars", "Total sugars", r"total\s+sugars?"),
    ("saturated_fat", "Saturated fat", r"saturated\s+fat"),
    ("trans_fat", "Trans fat", r"trans\s+fat"),
    ("total_fat", "Total fat", r"total\s+fat"),
    ("dietary_fibre", "Dietary fibre", r"(?:dietary\s+)?fib(?:re|er)"),
    ("sodium", "Sodium", r"sodium"),
    ("salt", "Salt", r"salt"),
)
NUTRIENT_PATTERN = re.compile(
    r"(?<!\w)(?P<label>" + "|".join(item[2] for item in NUTRIENT_ALIASES) + r")(?!\w)",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"^\d+(?:[.,]\d+)?$")
UNIT_PATTERN = re.compile(r"^(?:g|mg|kcal|kj|µg|ug|mcg|%)$", re.IGNORECASE)


@dataclass(frozen=True)
class TableWord:
    text: str
    confidence: float | None
    left: int
    top: int
    width: int
    height: int

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2


@dataclass(frozen=True)
class TableRow:
    words: tuple[TableWord, ...]

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


@dataclass(frozen=True)
class TableValue:
    original_text: str
    value: float | None
    unit: str | None
    basis: str | None
    column_type: str | None
    confidence: float | None
    source_coordinates: dict[str, int]
    review_required: bool
    ambiguity_warnings: tuple[str, ...]


@dataclass(frozen=True)
class TableFact:
    field: str
    label: str
    original_label: str
    values: tuple[TableValue, ...]
    source_text: str
    source_coordinates: dict[str, int]
    review_required: bool
    ambiguity_warnings: tuple[str, ...]


@dataclass(frozen=True)
class TableExtraction:
    detected: bool
    confidence: float | None
    facts: tuple[TableFact, ...]
    warnings: tuple[str, ...]


def _as_word(value: dict[str, Any]) -> TableWord | None:
    try:
        text = str(value["text"]).strip()
        if not text:
            return None
        confidence = value.get("confidence")
        return TableWord(
            text=text,
            confidence=float(confidence) if confidence is not None else None,
            left=int(value["left"]),
            top=int(value["top"]),
            width=int(value["width"]),
            height=int(value["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def words_from_evidence(evidence: dict[str, Any]) -> list[TableWord]:
    words: list[TableWord] = []
    for line in evidence.get("lines", []):
        if not isinstance(line, dict):
            continue
        for value in line.get("words", []):
            if isinstance(value, dict):
                word = _as_word(value)
                if word is not None:
                    words.append(word)
    return words


def group_words_into_rows(
    words: list[TableWord],
    image_width: int | None = None,
    image_height: int | None = None,
) -> list[TableRow]:
    if not words:
        return []
    heights = [word.height for word in words if word.height > 0]
    median_height = median(heights) if heights else 10
    tolerance = max(median_height * 0.55, (image_height or 0) * 0.008, 4)
    rows: list[list[TableWord]] = []
    row_centers: list[float] = []
    for word in sorted(words, key=lambda item: (item.center_y, item.left)):
        closest_index = min(
            range(len(row_centers)),
            key=lambda index: abs(row_centers[index] - word.center_y),
            default=None,
        )
        if closest_index is None or abs(row_centers[closest_index] - word.center_y) > tolerance:
            rows.append([word])
            row_centers.append(word.center_y)
            continue
        rows[closest_index].append(word)
        row_centers[closest_index] = sum(item.center_y for item in rows[closest_index]) / len(
            rows[closest_index]
        )
    return [
        TableRow(tuple(sorted(row, key=lambda item: item.left)))
        for row in sorted(rows, key=lambda value: min(word.center_y for word in value))
    ]


def _bounds(words: list[TableWord]) -> dict[str, int]:
    return {
        "left": min(word.left for word in words),
        "top": min(word.top for word in words),
        "right": max(word.left + word.width for word in words),
        "bottom": max(word.top + word.height for word in words),
    }


def _nutrient_match(row: TableRow) -> tuple[str, str, int] | None:
    match = NUTRIENT_PATTERN.search(row.text)
    if not match:
        return None
    label_text = match.group("label")
    normalized = re.sub(r"\s+", " ", label_text.lower()).strip()
    for field, label, pattern in NUTRIENT_ALIASES:
        if re.fullmatch(pattern, normalized, re.IGNORECASE):
            return field, label, match.start()
    return None


def _header_columns(rows: list[TableRow]) -> list[tuple[float, str, str | None]]:
    columns: list[tuple[float, str, str | None]] = []
    for row in rows:
        text = row.text.lower()
        if re.search(r"\b(?:nutrients?|nutrition)\b", text):
            anchor = next(
                (word for word in row.words if re.search(r"nutr", word.text, re.I)),
                row.words[0],
            )
            columns.append((anchor.center_x, "nutrient", None))
        hundred_match = re.search(r"\bper\s+100\s*(g|ml)\b", text)
        if hundred_match:
            anchor = next(
                (word for word in row.words if word.text == "100"),
                row.words[0],
            )
            columns.append(
                (
                    anchor.center_x,
                    "value",
                    "per_100_ml" if hundred_match.group(1).lower() == "ml" else "per_100_g",
                )
            )
        if re.search(r"\b(?:per\s+)?(?:serving|serve|portion)\b", text):
            anchor = next(
                (
                    word
                    for word in row.words
                    if re.search(r"serv|portion", word.text, re.I)
                ),
                row.words[-1],
            )
            columns.append((anchor.center_x, "value", "per_serving"))
        if re.search(r"(?:%?\s*rda|%rda)", text):
            anchor = next(
                (word for word in row.words if re.search(r"rda|%", word.text, re.I)),
                row.words[-1],
            )
            columns.append((anchor.center_x, "rda_percent", None))
    return columns


def _numeric_groups(words: list[TableWord]) -> list[list[TableWord]]:
    groups: list[list[TableWord]] = []
    index = 0
    while index < len(words):
        word = words[index]
        normalized = word.text.replace(",", ".")
        if not NUMBER_PATTERN.fullmatch(normalized):
            index += 1
            continue
        group = [word]
        if (
            index + 2 < len(words)
            and words[index + 1].text == "."
            and NUMBER_PATTERN.fullmatch(words[index + 2].text)
        ):
            group.extend(words[index + 1 : index + 3])
            index += 2
        if index + 1 < len(words) and UNIT_PATTERN.fullmatch(words[index + 1].text):
            group.append(words[index + 1])
            index += 1
        groups.append(group)
        index += 1
    return groups


def _value_from_group(
    group: list[TableWord],
    columns: list[tuple[float, str, str | None]],
) -> TableValue:
    number_text = "".join(
        word.text
        for word in group
        if word.text != "." and not UNIT_PATTERN.fullmatch(word.text)
    ).replace(",", ".")
    unit_words = [word.text for word in group if UNIT_PATTERN.fullmatch(word.text)]
    unit = unit_words[0].lower() if unit_words else None
    try:
        value = float(number_text)
    except ValueError:
        value = None
    center_x = sum(word.center_x for word in group) / len(group)
    column_type: str | None = None
    basis: str | None = None
    warnings: list[str] = []
    if columns:
        nearest = min(columns, key=lambda column: abs(column[0] - center_x))
        distance = abs(nearest[0] - center_x)
        if distance <= max(group[0].width * 3, 40):
            column_type, basis = nearest[1], nearest[2]
            if column_type.startswith("numeric_column_"):
                warnings.append("Serving basis is not identified by a table header.")
        else:
            warnings.append("Numeric value is not aligned with a known column.")
    else:
        warnings.append("No explicit serving column was detected.")
    if unit is None:
        warnings.append("Numeric value has no recognized unit.")
    confidence_values = [word.confidence for word in group if word.confidence is not None]
    return TableValue(
        original_text=" ".join(word.text for word in group),
        value=value,
        unit=unit,
        basis=basis,
        column_type=column_type,
        confidence=(
            round(sum(confidence_values) / len(confidence_values), 2)
            if confidence_values
            else None
        ),
        source_coordinates=_bounds(group),
        review_required=bool(warnings) or value is None,
        ambiguity_warnings=tuple(warnings),
    )


def _inferred_columns(rows: list[TableRow]) -> list[tuple[float, str, str | None]]:
    centers: list[float] = []
    for row in rows:
        match = _nutrient_match(row)
        if match is None:
            continue
        centers.extend(
            sum(word.center_x for word in group) / len(group)
            for group in _numeric_groups(list(row.words))
        )
    if len(centers) < 2:
        return []
    centers.sort()
    clusters: list[list[float]] = []
    tolerance = max(25.0, (centers[-1] - centers[0]) * 0.08)
    for center in centers:
        if not clusters or abs(center - sum(clusters[-1]) / len(clusters[-1])) > tolerance:
            clusters.append([center])
        else:
            clusters[-1].append(center)
    if len(clusters) < 2:
        return []
    return [
        (sum(cluster) / len(cluster), f"numeric_column_{index + 1}", None)
        for index, cluster in enumerate(clusters)
    ]


def extract_table_nutrition(
    evidence: dict[str, Any] | None,
    image_width: int | None = None,
    image_height: int | None = None,
) -> TableExtraction:
    if not evidence:
        return TableExtraction(False, None, (), ())
    words = words_from_evidence(evidence)
    rows = group_words_into_rows(words, image_width, image_height)
    nutrient_rows = [row for row in rows if _nutrient_match(row) is not None]
    if len(nutrient_rows) < 2:
        return TableExtraction(False, None, (), ("Fewer than two nutrient rows were detected.",))
    numeric_nutrient_rows = [
        row for row in nutrient_rows if _numeric_groups(list(row.words))
    ]
    if len(numeric_nutrient_rows) < 2:
        return TableExtraction(
            False,
            None,
            (),
            ("Fewer than two numeric nutrient rows were detected.",),
        )

    columns = _header_columns(rows)
    if not columns:
        columns = _inferred_columns(nutrient_rows)
    facts: list[TableFact] = []
    for row in nutrient_rows:
        match = _nutrient_match(row)
        if match is None:
            continue
        field, label, _ = match
        numeric_words = _numeric_groups(list(row.words))
        values = tuple(_value_from_group(group, columns) for group in numeric_words)
        warnings = list(
            warning for value in values for warning in value.ambiguity_warnings
        )
        if len(values) > 1 and (
            not columns or any(value.basis is None for value in values)
        ):
            warnings.append("Multiple values have no reliable serving-column association.")
        facts.append(
            TableFact(
                field=field,
                label=label,
                original_label=label,
                values=values,
                source_text=row.text,
                source_coordinates=_bounds(list(row.words)),
                review_required=not values or bool(warnings),
                ambiguity_warnings=tuple(dict.fromkeys(warnings)),
            )
        )
    if not facts:
        return TableExtraction(False, None, (), ("No numeric nutrient rows were detected.",))
    duplicate_fields = {fact.field for fact in facts if sum(item.field == fact.field for item in facts) > 1}
    if duplicate_fields:
        facts = [
            TableFact(
                field=fact.field,
                label=fact.label,
                original_label=fact.original_label,
                values=fact.values,
                source_text=fact.source_text,
                source_coordinates=fact.source_coordinates,
                review_required=True,
                ambiguity_warnings=tuple(
                    dict.fromkeys((*fact.ambiguity_warnings, "Duplicate nutrient row detected."))
                ),
            )
            for fact in facts
        ]
    confidence = min(1.0, len(facts) / max(len(nutrient_rows), 1))
    return TableExtraction(True, round(confidence, 3), tuple(facts), ())
