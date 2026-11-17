from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.preprocessing import prepare_candidates


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
