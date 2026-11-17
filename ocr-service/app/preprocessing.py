from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class PreparedImage:
    image: np.ndarray
    width: int
    height: int
    scale: float
    deskew_angle: float
    strategy: str


def _deskew(grayscale: np.ndarray) -> tuple[np.ndarray, float]:
    threshold = cv2.threshold(
        grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]
    if cv2.countNonZero(threshold) < 20:
        return grayscale, 0.0
    height, width = grayscale.shape[:2]
    best_angle = 0.0
    best_score = -1.0
    for angle in np.arange(-8.0, 8.1, 0.5):
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), float(angle), 1.0)
        rotated = cv2.warpAffine(
            threshold,
            matrix,
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        row_projection = np.sum(rotated > 0, axis=1)
        score = float(np.sum(np.square(row_projection)))
        if score > best_score:
            best_score = score
            best_angle = float(angle)
    if abs(best_angle) < 0.4:
        return grayscale, 0.0
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), best_angle, 1.0)
    rotated = cv2.warpAffine(
        grayscale,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, round(best_angle, 2)


def prepare_candidates(content: bytes) -> tuple[list[PreparedImage], tuple[int, int]]:
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a valid image.")
    original_height, original_width = image.shape[:2]
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    target_width = 1600
    scale = max(1.0, min(3.0, target_width / max(original_width, 1)))
    if scale > 1:
        grayscale = cv2.resize(
            grayscale, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
        )
    denoised = cv2.fastNlMeansDenoising(grayscale, None, 10, 7, 21)
    aligned, angle = _deskew(denoised)
    adaptive = cv2.adaptiveThreshold(
        aligned,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    otsu = cv2.threshold(aligned, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return [
        PreparedImage(
            image=adaptive,
            width=original_width,
            height=original_height,
            scale=round(scale, 2),
            deskew_angle=angle,
            strategy="resize, grayscale, denoise, deskew, adaptive threshold",
        ),
        PreparedImage(
            image=otsu,
            width=original_width,
            height=original_height,
            scale=round(scale, 2),
            deskew_angle=angle,
            strategy="resize, grayscale, denoise, deskew, Otsu threshold",
        ),
    ], (original_width, original_height)
