from io import BytesIO

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

app = FastAPI(title="AharaIQ OCR Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "aharaiq-ocr", "status": "ok"}


@app.post("/ocr")
async def extract_text(file: UploadFile = File(...)) -> dict[str, str]:
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Only JPG and PNG images are supported.")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB.")
    try:
        Image.open(BytesIO(content)).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.") from exc
    raise HTTPException(
        status_code=503,
        detail="OCR is not configured yet. Install Tesseract and enable the extraction pipeline.",
    )
