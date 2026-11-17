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
    perspective_applied: bool = False
    perspective_confidence: float | None = None
    perspective_corners: tuple[tuple[int, int], ...] | None = None
    coordinate_space: str = "selected_candidate_pixels"


MAX_CORRECTED_WIDTH = 2400
MAX_CORRECTED_HEIGHT = 2400
MAX_CORRECTED_PIXELS = 4_000_000


def _order_corners(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(differences)]
    ordered[3] = points[np.argmax(differences)]
    return ordered


def _corner_angle(first: np.ndarray, vertex: np.ndarray, last: np.ndarray) -> float:
    first_vector = first - vertex
    last_vector = last - vertex
    denominator = np.linalg.norm(first_vector) * np.linalg.norm(last_vector)
    if denominator == 0:
        return 0.0
    cosine = np.clip(np.dot(first_vector, last_vector) / denominator, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def _validate_quadrilateral(
    points: np.ndarray, image_shape: tuple[int, int]
) -> tuple[np.ndarray, float] | None:
    if points.shape != (4, 2) or not np.isfinite(points).all():
        return None
    ordered = _order_corners(points.astype(np.float32))
    if len({(round(float(x)), round(float(y))) for x, y in ordered}) != 4:
        return None
    if not cv2.isContourConvex(ordered.astype(np.int32)):
        return None

    height, width = image_shape[:2]
    area = abs(float(cv2.contourArea(ordered)))
    area_ratio = area / max(float(width * height), 1.0)
    if area_ratio < 0.08 or area_ratio > 0.98:
        return None

    edges = np.linalg.norm(np.roll(ordered, -1, axis=0) - ordered, axis=1)
    if np.min(edges) < max(12.0, min(width, height) * 0.04):
        return None
    if float(np.max(edges) / np.min(edges)) > 12.0:
        return None

    angles = [
        _corner_angle(ordered[(index - 1) % 4], ordered[index], ordered[(index + 1) % 4])
        for index in range(4)
    ]
    if min(angles) < 45.0 or max(angles) > 135.0:
        return None

    angle_score = 1.0 - min(
        sum(abs(angle - 90.0) for angle in angles) / 360.0, 1.0
    )
    edge_score = min(float(np.min(edges) / np.max(edges)), 1.0)
    area_score = min(area_ratio / 0.5, 1.0)
    confidence = round(0.45 * angle_score + 0.25 * edge_score + 0.30 * area_score, 3)
    if confidence < 0.55:
        return None
    return ordered, confidence


def _detect_quadrilateral(grayscale: np.ndarray) -> tuple[np.ndarray, float] | None:
    blurred = cv2.GaussianBlur(grayscale, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    candidates: list[tuple[np.ndarray, float]] = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        approximated = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
        if len(approximated) != 4:
            continue
        validated = _validate_quadrilateral(
            approximated.reshape(4, 2).astype(np.float32), grayscale.shape
        )
        if validated is not None:
            candidates.append(validated)
    if not candidates:
        return None
    candidates.sort(key=lambda candidate: candidate[1], reverse=True)
    if len(candidates) > 1 and candidates[0][1] - candidates[1][1] < 0.03:
        return None
    return candidates[0]


def _perspective_dimensions(corners: np.ndarray) -> tuple[int, int] | None:
    widths = [
        np.linalg.norm(corners[1] - corners[0]),
        np.linalg.norm(corners[2] - corners[3]),
    ]
    heights = [
        np.linalg.norm(corners[3] - corners[0]),
        np.linalg.norm(corners[2] - corners[1]),
    ]
    target_width = max(1, int(round(max(widths))))
    target_height = max(1, int(round(max(heights))))
    scale = min(
        1.0,
        MAX_CORRECTED_WIDTH / target_width,
        MAX_CORRECTED_HEIGHT / target_height,
        np.sqrt(MAX_CORRECTED_PIXELS / max(target_width * target_height, 1)),
    )
    target_width = int(round(target_width * scale))
    target_height = int(round(target_height * scale))
    if target_width < 80 or target_height < 80:
        return None
    return target_width, target_height


def _warp_perspective(
    grayscale: np.ndarray, corners: np.ndarray
) -> np.ndarray | None:
    dimensions = _perspective_dimensions(corners)
    if dimensions is None:
        return None
    target_width, target_height = dimensions
    destination = np.array(
        [
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(corners.astype(np.float32), destination)
    return cv2.warpPerspective(
        grayscale,
        transform,
        (target_width, target_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


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
    candidates = [
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
    ]
    detected = _detect_quadrilateral(denoised)
    if detected is None:
        return candidates, (original_width, original_height)

    corners, perspective_confidence = detected
    corrected = _warp_perspective(denoised, corners)
    if corrected is None:
        return candidates, (original_width, original_height)
    corrected_aligned, corrected_angle = _deskew(corrected)
    corrected_adaptive = cv2.adaptiveThreshold(
        corrected_aligned,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    corrected_otsu = cv2.threshold(
        corrected_aligned, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]
    corner_metadata = tuple(
        (int(round(point[0])), int(round(point[1]))) for point in corners
    )
    candidates.extend(
        [
            PreparedImage(
                image=corrected_adaptive,
                width=original_width,
                height=original_height,
                scale=round(scale, 2),
                deskew_angle=corrected_angle,
                strategy="perspective, resize, grayscale, denoise, deskew, adaptive threshold",
                perspective_applied=True,
                perspective_confidence=perspective_confidence,
                perspective_corners=corner_metadata,
                coordinate_space="selected_candidate_pixels",
            ),
            PreparedImage(
                image=corrected_otsu,
                width=original_width,
                height=original_height,
                scale=round(scale, 2),
                deskew_angle=corrected_angle,
                strategy="perspective, resize, grayscale, denoise, deskew, Otsu threshold",
                perspective_applied=True,
                perspective_confidence=perspective_confidence,
                perspective_corners=corner_metadata,
                coordinate_space="selected_candidate_pixels",
            ),
        ]
    )
    return candidates, (original_width, original_height)
