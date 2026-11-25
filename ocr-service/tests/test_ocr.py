from io import BytesIO
import hashlib

from fastapi.testclient import TestClient
from PIL import Image

from app.main import (
    OcrLine,
    OcrResult,
    OcrWord,
    _nutrition_rows,
    _score_ocr_result,
    app,
    extract_best_ocr,
    extract_ocr_result,
)
from app.preprocessing import PreparedImage

client = TestClient(app)


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (20, 20), "white").save(output, format="PNG")
    return output.getvalue()


def candidate(strategy: str) -> PreparedImage:
    return PreparedImage(
        image=Image.new("L", (20, 20)),
        width=20,
        height=20,
        scale=1.0,
        deskew_angle=0.0,
        strategy=strategy,
    )


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


def test_candidate_score_prefers_clean_food_label_text() -> None:
    clean = OcrResult(
        text="Nutrition Information\nIngredients: flour, sugar\nProtein 10 g",
        average_confidence=92.0,
        median_confidence=92.0,
        low_confidence_proportion=0.0,
        confidences=(95.0, 90.0, 91.0, 93.0, 89.0, 94.0, 92.0),
        word_count=9,
        line_count=3,
        readable_line_count=3,
        lines=(),
    )
    noisy = OcrResult(
        text="@@ ## 1I1I !!! xqz %% ^^^ ???",
        average_confidence=88.0,
        median_confidence=44.0,
        low_confidence_proportion=1.0,
        confidences=(40.0, 45.0, 48.0, 35.0, 42.0, 44.0, 47.0),
        word_count=8,
        line_count=1,
        readable_line_count=1,
        lines=(),
    )

    assert _score_ocr_result(clean) > _score_ocr_result(noisy)


def test_empty_candidate_score_is_unusable() -> None:
    result = OcrResult(
        text="",
        average_confidence=None,
        median_confidence=None,
        low_confidence_proportion=None,
        confidences=(),
        word_count=0,
        line_count=0,
        readable_line_count=0,
        lines=(),
    )

    assert _score_ocr_result(result) == float("-inf")


def test_ocr_result_preserves_word_coordinates_and_confidence_distribution(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.pytesseract.image_to_data",
        lambda image, config, output_type: {
            "text": ["Protein", "10", "g"],
            "conf": ["91.0", "88.0", "90.0"],
            "block_num": [1, 1, 1],
            "par_num": [1, 1, 1],
            "line_num": [1, 1, 1],
            "left": [10, 90, 120],
            "top": [20, 20, 20],
            "width": [70, 25, 12],
            "height": [18, 18, 18],
        },
    )

    result = extract_ocr_result(Image.new("L", (200, 100)))

    assert result.text == "Protein 10 g"
    assert result.median_confidence == 90.0
    assert result.low_confidence_proportion == 0.0
    assert result.lines[0].words[1].left == 90
    assert result.lines[0].words[1].confidence == 88.0


def test_nutrition_rows_include_text_confidence_and_bounds() -> None:
    line = OcrLine(
        text="Protein 10 g",
        words=(
            OcrWord("Protein", 90.0, 10, 20, 70, 18),
            OcrWord("10", 88.0, 90, 20, 25, 18),
            OcrWord("g", 92.0, 120, 20, 12, 18),
        ),
    )
    result = OcrResult(
        "Protein 10 g",
        90.0,
        90.0,
        0.0,
        (90.0, 88.0, 92.0),
        3,
        1,
        1,
        (line,),
    )

    rows = _nutrition_rows(result)

    assert rows == [
        {
            "text": "Protein 10 g",
            "confidence": 90.0,
            "wordCount": 3,
            "bounds": {"left": 10, "top": 20, "right": 132, "bottom": 38},
        }
    ]


def test_ocr_endpoint_preserves_original_provenance_and_coordinate_metadata(
    monkeypatch,
) -> None:
    content = image_bytes()
    prepared = candidate("original")
    result = OcrResult(
        "Protein 10 g",
        90.0,
        90.0,
        0.0,
        (90.0,),
        3,
        1,
        1,
        (),
    )
    monkeypatch.setattr("app.main.TESSERACT_PATH", "configured")
    monkeypatch.setattr(
        "app.main.prepare_candidates", lambda value: ([prepared], (20, 20))
    )
    monkeypatch.setattr(
        "app.main.extract_best_ocr",
        lambda candidates: ("Protein 10 g", 90.0, prepared, result),
    )

    response = client.post(
        "/ocr",
        files={"file": ("label.png", content, "image/png")},
    )

    metadata = response.json()["metadata"]
    assert response.status_code == 200
    assert metadata["width"] == 20
    assert metadata["height"] == 20
    assert metadata["originalSha256"] == hashlib.sha256(content).hexdigest()
    assert metadata["perspectiveCorrectionApplied"] is False
    assert metadata["coordinateSpace"] == "selected_candidate_pixels"


def test_candidate_selection_handles_empty_and_competing_candidates(monkeypatch) -> None:
    prepared = [candidate("empty"), candidate("clean"), candidate("noisy")]
    results = iter(
        [
            OcrResult("", None, None, None, (), 0, 0, 0, ()),
            OcrResult(
                "Ingredients: flour\nProtein 10 g",
                90.0,
                90.5,
                0.0,
                (90.0, 91.0, 89.0, 92.0),
                4,
                2,
                2,
                (),
            ),
            OcrResult(
                "!!! ??? ### xxxxxxxxxxxxxxxxx",
                86.0,
                41.0,
                1.0,
                (35.0, 40.0, 45.0, 42.0),
                4,
                1,
                1,
                (),
            ),
        ]
    )
    monkeypatch.setattr(
        "app.main.extract_ocr_result",
        lambda image: next(results),
    )

    text, confidence, selected, result = extract_best_ocr(prepared)

    assert text == "Ingredients: flour\nProtein 10 g"
    assert confidence == 90.0
    assert selected.strategy == "clean"
    assert result.text == text


def test_candidate_selection_returns_empty_result_when_all_candidates_are_empty(
    monkeypatch,
) -> None:
    prepared = [candidate("first"), candidate("second")]
    monkeypatch.setattr(
        "app.main.extract_ocr_result",
        lambda image: OcrResult("", None, None, None, (), 0, 0, 0, ()),
    )

    text, confidence, selected, result = extract_best_ocr(prepared)

    assert text == ""
    assert confidence is None
    assert selected.strategy == "first"
    assert result.text == ""
