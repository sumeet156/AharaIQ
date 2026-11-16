import os
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pytesseract import Output
from pytesseract.pytesseract import TesseractNotFoundError

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


def preprocess_image(content: bytes) -> tuple[np.ndarray, tuple[int, int]]:
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a valid image.")
    height, width = image.shape[:2]
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(grayscale, None, 10, 7, 21)
    processed = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return processed, (width, height)


def extract_ocr(processed: np.ndarray) -> tuple[str, float | None]:
    data: dict[str, Any] = pytesseract.image_to_data(
        processed,
        config="--oem 3 --psm 6",
        output_type=Output.DICT,
    )
    words = []
    confidences = []
    for text, confidence in zip(data["text"], data["conf"]):
        cleaned = text.strip()
        if cleaned:
            words.append(cleaned)
        try:
            numeric_confidence = float(confidence)
        except (TypeError, ValueError):
            continue
        if numeric_confidence >= 0:
            confidences.append(numeric_confidence)
    return " ".join(words), round(sum(confidences) / len(confidences), 2) if confidences else None


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
        processed, (width, height) = preprocess_image(content)
        text, confidence = extract_ocr(processed)
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
            "preprocessing": "grayscale, denoise, Otsu threshold",
            "averageConfidence": confidence,
        },
    }
