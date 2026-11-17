import os
import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import pytesseract

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pytesseract import Output
from pytesseract.pytesseract import TesseractNotFoundError
from .parser.models import ParseRequest, ParseResponse
from .parser.parser import parse_label
from .preprocessing import PreparedImage, prepare_candidates

app = FastAPI(title="AharaIQ OCR Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("OCR_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def configure_tesseract() -> str | None:
    configured = os.getenv("TESSERACT_CMD")
    candidates = [configured] if configured else []
    candidates.extend(
        [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return candidate
    return None


TESSERACT_PATH = configure_tesseract()


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "service": "aharaiq-ocr",
        "status": "ok" if TESSERACT_PATH else "degraded",
        "tesseractConfigured": bool(TESSERACT_PATH),
    }


@dataclass(frozen=True)
class OcrWord:
    text: str
    confidence: float | None
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class OcrLine:
    text: str
    words: tuple[OcrWord, ...]


@dataclass(frozen=True)
class OcrResult:
    text: str
    average_confidence: float | None
    median_confidence: float | None
    low_confidence_proportion: float | None
    confidences: tuple[float, ...]
    word_count: int
    line_count: int
    readable_line_count: int
    lines: tuple[OcrLine, ...]


FOOD_LABEL_KEYWORDS = (
    "ingredients",
    "energy",
    "protein",
    "carbohydrates",
    "sugars",
    "fat",
    "sodium",
)
ALLOWED_TEXT_PUNCTUATION = set(".,:;/%()[]+-")


def extract_ocr_result(processed: np.ndarray) -> OcrResult:
    data: dict[str, Any] = pytesseract.image_to_data(
        processed,
        config="--oem 3 --psm 6",
        output_type=Output.DICT,
    )
    lines: list[OcrLine] = []
    current_words: list[OcrWord] = []
    current_key: tuple[int, int, int] | None = None
    confidences: list[float] = []
    for index, (text, confidence) in enumerate(zip(data["text"], data["conf"])):
        cleaned = text.strip()
        if cleaned:
            key = (
                data["block_num"][index],
                data["par_num"][index],
                data["line_num"][index],
            )
            if current_key is not None and key != current_key and current_words:
                lines.append(
                    OcrLine(
                        text=" ".join(word.text for word in current_words),
                        words=tuple(current_words),
                    )
                )
                current_words = []
            current_key = key
            try:
                numeric_confidence = float(confidence)
            except (TypeError, ValueError):
                numeric_confidence = None
            current_words.append(
                OcrWord(
                    text=cleaned,
                    confidence=(
                        numeric_confidence
                        if numeric_confidence is not None and numeric_confidence >= 0
                        else None
                    ),
                    left=int(data["left"][index]),
                    top=int(data["top"][index]),
                    width=int(data["width"][index]),
                    height=int(data["height"][index]),
                )
            )
            if numeric_confidence is not None and numeric_confidence >= 0:
                confidences.append(numeric_confidence)
    if current_words:
        lines.append(
            OcrLine(
                text=" ".join(word.text for word in current_words),
                words=tuple(current_words),
            )
        )
    text = "\n".join(line.text for line in lines)
    readable_lines = sum(1 for line in lines if re.search(r"[A-Za-z]", line.text))
    confidence_median = median(confidences) if confidences else None
    low_confidence_proportion = (
        sum(confidence < 50 for confidence in confidences) / len(confidences)
        if confidences
        else None
    )
    return OcrResult(
        text=text,
        average_confidence=(
            round(sum(confidences) / len(confidences), 2) if confidences else None
        ),
        median_confidence=(
            round(confidence_median, 2) if confidence_median is not None else None
        ),
        low_confidence_proportion=(
            round(low_confidence_proportion, 4)
            if low_confidence_proportion is not None
            else None
        ),
        confidences=tuple(confidences),
        word_count=sum(len(line.words) for line in lines),
        line_count=len(lines),
        readable_line_count=readable_lines,
        lines=tuple(lines),
    )


def extract_ocr(processed: np.ndarray) -> tuple[str, float | None]:
    result = extract_ocr_result(processed)
    return result.text, result.average_confidence


def _score_ocr_result(result: OcrResult) -> float:
    if not result.text.strip() or not result.confidences or result.word_count == 0:
        return float("-inf")

    mean_confidence = sum(result.confidences) / len(result.confidences)
    median_confidence = median(result.confidences)
    low_confidence_ratio = sum(
        confidence < 50 for confidence in result.confidences
    ) / len(result.confidences)
    readable_line_ratio = (
        result.readable_line_count / result.line_count if result.line_count else 0.0
    )
    alphanumeric_characters = sum(character.isalnum() for character in result.text)
    alphabetic_characters = sum(character.isalpha() for character in result.text)
    significant_characters = sum(
        not character.isspace() for character in result.text
    )
    suspicious_characters = sum(
        not character.isalnum()
        and not character.isspace()
        and character not in ALLOWED_TEXT_PUNCTUATION
        for character in result.text
    )
    alphabetic_ratio = (
        alphabetic_characters / alphanumeric_characters
        if alphanumeric_characters
        else 0.0
    )
    suspicious_ratio = (
        suspicious_characters / significant_characters
        if significant_characters
        else 1.0
    )
    normalized_text = result.text.lower()
    keyword_hits = sum(
        bool(re.search(rf"\b{re.escape(keyword)}\b", normalized_text))
        for keyword in FOOD_LABEL_KEYWORDS
    )

    return (
        mean_confidence * 0.35
        + median_confidence * 0.25
        + (1 - low_confidence_ratio) * 15
        + min(result.word_count, 30) / 30 * 8
        + readable_line_ratio * 8
        + alphabetic_ratio * 8
        + keyword_hits * 2
        - suspicious_ratio * 20
    )


NUTRITION_ROW_PATTERN = re.compile(
    r"\b(?:energy|protein|carbohydrates?|sugars?|fats?|sodium|salt|fibre|fiber)\b"
    r".*(?:\d+(?:[.,]\d+)?\s*(?:kcal|kj|g|mg|ml|µg|ug|mcg)\b)",
    re.IGNORECASE,
)


def _nutrition_rows(result: OcrResult) -> list[dict[str, Any]]:
    rows = []
    for line in result.lines:
        if not NUTRITION_ROW_PATTERN.search(line.text):
            continue
        confidence_values = [
            word.confidence for word in line.words if word.confidence is not None
        ]
        rows.append(
            {
                "text": line.text,
                "confidence": (
                    round(sum(confidence_values) / len(confidence_values), 2)
                    if confidence_values
                    else None
                ),
                "wordCount": len(line.words),
                "bounds": {
                    "left": min(word.left for word in line.words),
                    "top": min(word.top for word in line.words),
                    "right": max(word.left + word.width for word in line.words),
                    "bottom": max(word.top + word.height for word in line.words),
                },
            }
        )
    return rows


def _ocr_evidence(result: OcrResult) -> dict[str, Any]:
    return {
        "lines": [
            {
                "text": line.text,
                "words": [
                    {
                        "text": word.text,
                        "confidence": word.confidence,
                        "left": word.left,
                        "top": word.top,
                        "width": word.width,
                        "height": word.height,
                    }
                    for word in line.words
                ],
            }
            for line in result.lines
        ]
    }


def extract_best_ocr(
    candidates: list[PreparedImage],
) -> tuple[str, float | None, PreparedImage, OcrResult]:
    if not candidates:
        raise ValueError("No OCR preprocessing candidates were generated.")

    results: list[tuple[float, OcrResult, PreparedImage]] = []
    for candidate in candidates:
        result = extract_ocr_result(candidate.image)
        results.append((_score_ocr_result(result), result, candidate))

    usable_results = [result for result in results if result[0] != float("-inf")]
    if not usable_results:
        empty_result = OcrResult("", None, None, None, (), 0, 0, 0, ())
        return "", None, candidates[0], empty_result

    _, selected, candidate = max(usable_results, key=lambda result: result[0])
    return selected.text, selected.average_confidence, candidate, selected


@app.post("/ocr")
async def extract_text(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Only JPG, JPEG and PNG images are supported.")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB.")
    try:
        Image.open(BytesIO(content)).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.") from exc
    if not TESSERACT_PATH:
        raise HTTPException(status_code=503, detail="Tesseract OCR is not installed or configured.")
    try:
        candidates, (width, height) = prepare_candidates(content)
        text, confidence, selected, selected_result = extract_best_ocr(candidates)
    except TesseractNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Tesseract OCR could not be started.") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"OCR could not process this image: {exc}") from exc
    return {
        "text": text,
        "metadata": {
            "filename": file.filename,
            "contentType": file.content_type,
            "width": width,
            "height": height,
            "bytes": len(content),
            "originalSha256": hashlib.sha256(content).hexdigest(),
            "preprocessing": selected.strategy,
            "scale": selected.scale,
            "deskewAngle": selected.deskew_angle,
            "candidateCount": len(candidates),
            "averageConfidence": confidence,
            "perspectiveCorrectionApplied": selected.perspective_applied,
            "perspectiveConfidence": selected.perspective_confidence,
            "perspectiveCorners": selected.perspective_corners,
            "perspectiveCornerCoordinateSpace": (
                "resized_source_pixels"
                if selected.perspective_corners is not None
                else None
            ),
            "coordinateSpace": selected.coordinate_space,
            "medianConfidence": selected_result.median_confidence,
            "lowConfidenceProportion": selected_result.low_confidence_proportion,
            "wordCount": selected_result.word_count,
            "lineCount": selected_result.line_count,
            "nutritionRows": _nutrition_rows(selected_result),
            "ocrEvidence": _ocr_evidence(selected_result),
        },
    }


@app.post("/parse", response_model=ParseResponse)
def parse_text(request: ParseRequest) -> ParseResponse:
    return parse_label(request.rawText, request.source)
