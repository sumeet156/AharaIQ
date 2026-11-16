from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (20, 20), "white").save(output, format="PNG")
    return output.getvalue()


def test_rejects_non_image_upload() -> None:
    response = client.post(
        "/ocr",
        files={"file": ("label.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415


def test_rejects_invalid_image_bytes() -> None:
    response = client.post(
        "/ocr",
        files={"file": ("label.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400


def test_health_reports_tesseract_configuration() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "aharaiq-ocr"
