from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.preprocessing import (
    _detect_quadrilateral,
    _validate_quadrilateral,
    _warp_perspective,
    prepare_candidates,
)


def image_bytes(width: int = 480, height: int = 320, angle: float = 0) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), "Nutrition Protein 10 g", fill="black")
    if angle:
        image = image.rotate(angle, expand=True, fillcolor="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_small_images_are_upscaled_and_have_multiple_threshold_candidates() -> None:
    candidates, dimensions = prepare_candidates(image_bytes())
    assert dimensions == (480, 320)
    assert len(candidates) == 2
    assert candidates[0].scale > 1
    assert candidates[0].image.shape[1] > dimensions[0]
    assert "adaptive threshold" in candidates[0].strategy
    assert "Otsu threshold" in candidates[1].strategy


def test_rotated_images_are_deskewed_when_angle_is_small() -> None:
    candidates, _ = prepare_candidates(image_bytes(angle=4))
    assert any(abs(candidate.deskew_angle) > 0 for candidate in candidates)


def test_invalid_image_bytes_raise_value_error() -> None:
    try:
        prepare_candidates(b"not an image")
    except ValueError as error:
        assert "valid image" in str(error)
    else:
        raise AssertionError("Invalid image bytes should fail preprocessing")


def perspective_label_bytes() -> bytes:
    source = np.full((300, 400), 255, dtype=np.uint8)
    cv2.rectangle(source, (5, 5), (394, 294), 0, 8)
    cv2.putText(
        source,
        "Protein 10 g",
        (55, 155),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        0,
        2,
        cv2.LINE_AA,
    )
    corners = np.array(
        [[120, 80], [580, 40], [620, 430], [80, 450]], dtype=np.float32
    )
    source_corners = np.array(
        [[0, 0], [399, 0], [399, 299], [0, 299]], dtype=np.float32
    )
    transform = cv2.getPerspectiveTransform(source_corners, corners)
    image = cv2.warpPerspective(source, transform, (700, 500), borderValue=0)
    output = BytesIO()
    Image.fromarray(image).save(output, format="PNG")
    return output.getvalue()


def test_detects_and_warps_synthetic_perspective_label() -> None:
    image = cv2.imdecode(
        np.frombuffer(perspective_label_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE
    )

    detected = _detect_quadrilateral(image)

    assert detected is not None
    corners, confidence = detected
    assert confidence > 0.55
    corrected = _warp_perspective(image, corners)
    assert corrected is not None
    assert corrected.shape[1] > 300
    assert corrected.shape[0] > 200


def test_rejects_invalid_duplicate_collinear_and_extreme_quadrilaterals() -> None:
    invalid_shapes = [
        np.array([[10, 10], [100, 10], [100, 100], [10, 10]], dtype=np.float32),
        np.array([[10, 10], [100, 10], [190, 10], [10, 100]], dtype=np.float32),
        np.array([[10, 10], [100, 10], [110, 30], [10, 100]], dtype=np.float32),
    ]

    for points in invalid_shapes:
        assert _validate_quadrilateral(points, (500, 700)) is None


def test_no_detection_keeps_original_candidates(monkeypatch) -> None:
    monkeypatch.setattr("app.preprocessing._detect_quadrilateral", lambda image: None)

    candidates, _ = prepare_candidates(image_bytes())

    assert len(candidates) == 2
    assert all(not candidate.perspective_applied for candidate in candidates)


def test_successful_detection_adds_candidates_without_removing_originals() -> None:
    candidates, dimensions = prepare_candidates(perspective_label_bytes())

    assert dimensions == (700, 500)
    assert len(candidates) >= 4
    assert any(not candidate.perspective_applied for candidate in candidates)
    corrected = [candidate for candidate in candidates if candidate.perspective_applied]
    assert corrected
    assert all(candidate.perspective_confidence is not None for candidate in corrected)
    assert all(candidate.perspective_corners is not None for candidate in corrected)
