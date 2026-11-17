import os
import hashlib
from io import BytesIO
from pathlib import Path
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


def extract_ocr(processed: np.ndarray) -> tuple[str, float | None]:
    data: dict[str, Any] = pytesseract.image_to_data(
        processed,
        config="--oem 3 --psm 6",
        output_type=Output.DICT,
    )
    lines: list[str] = []
    current_line: list[str] = []
    current_key: tuple[int, int, int] | None = None
    confidences = []
    for index, (text, confidence) in enumerate(zip(data["text"], data["conf"])):
        cleaned = text.strip()
        if cleaned:
            key = (
                data["block_num"][index],
                data["par_num"][index],
                data["line_num"][index],
            )
            if current_key is not None and key != current_key and current_line:
                lines.append(" ".join(current_line))
                current_line = []
            current_key = key
            current_line.append(cleaned)
        try:
            numeric_confidence = float(confidence)
        except (TypeError, ValueError):
            continue
        if numeric_confidence >= 0:
            confidences.append(numeric_confidence)
    if current_line:
        lines.append(" ".join(current_line))
    return "\n".join(lines), round(sum(confidences) / len(confidences), 2) if confidences else None


def extract_best_ocr(candidates: list[PreparedImage]) -> tuple[str, float | None, PreparedImage]:
    results = []
    for candidate in candidates:
        text, confidence = extract_ocr(candidate.image)
        quality = (confidence or 0.0) + min(len(text), 300) / 300
        results.append((quality, text, confidence, candidate))
    return max(results, key=lambda result: result[0])[1:]


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
        text, confidence, selected = extract_best_ocr(candidates)
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
        },
    }


@app.post("/parse", response_model=ParseResponse)
def parse_text(request: ParseRequest) -> ParseResponse:
    return parse_label(request.rawText, request.source)
