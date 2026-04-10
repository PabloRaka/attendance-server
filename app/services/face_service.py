import os
import cv2
import numpy as np
import asyncio
import logging

logger = logging.getLogger(__name__)

# ── Model paths ─────────────────────────────────────────────────────────────────
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "models")
_YUNET_PATH  = os.path.join(_ASSETS_DIR, "face_detection_yunet_2023mar.onnx")
_SFACE_PATH  = os.path.join(_ASSETS_DIR, "face_recognition_sface_2021dec.onnx")

# Validate model files exist
if not os.path.exists(_YUNET_PATH):
    raise FileNotFoundError(f"YuNet model not found at: {_YUNET_PATH}")
if not os.path.exists(_SFACE_PATH):
    raise FileNotFoundError(f"SFace model not found at: {_SFACE_PATH}")

# ── Lazy-loaded singleton models (thread-safe creation at first use) ─────────────
_yunet_detector = None
_sface_recognizer = None

def _get_yunet(width: int = 640, height: int = 480) -> cv2.FaceDetectorYN:
    """Return a YuNet detector configured for the given image size."""
    return cv2.FaceDetectorYN.create(
        _YUNET_PATH,
        "",
        (width, height),
        score_threshold=0.6,
        nms_threshold=0.3,
        top_k=5,
    )

def _get_sface() -> cv2.FaceRecognizerSF:
    global _sface_recognizer
    if _sface_recognizer is None:
        _sface_recognizer = cv2.FaceRecognizerSF.create(_SFACE_PATH, "")
    return _sface_recognizer


# ── Core helpers ─────────────────────────────────────────────────────────────────

def _detect_face(image: np.ndarray):
    """
    Detect the largest/highest-confidence face in *image*.
    Returns the 5-point face box row (1×15 float) or None.
    """
    h, w = image.shape[:2]
    detector = _get_yunet(w, h)
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        return None
    # faces sorted by confidence (descending) by OpenCV already
    return faces[0:1]   # keep as (1, 15) ndarray


def _align_and_encode(image: np.ndarray, face_box) -> np.ndarray | None:
    """
    Align the detected face and extract the 128-d feature embedding.
    face_box must be the (1, 15) output row from YuNet.
    """
    try:
        sface = _get_sface()
        aligned = sface.alignCrop(image, face_box)
        feature = sface.feature(aligned)
        return feature          # shape (1, 128)
    except Exception as e:
        logger.error("SFace encoding error: %s", e)
        return None


def _cosine_similarity(feat1: np.ndarray, feat2: np.ndarray) -> float:
    """Return cosine similarity in [0, 1] between two SFace feature vectors."""
    sface = _get_sface()
    # cv2.FaceRecognizerSF.match returns raw cosine score in [-1, 1]
    score = sface.match(feat1, feat2, cv2.FaceRecognizerSF_FR_COSINE)
    # Normalise to [0, 1]
    return float((score + 1.0) / 2.0)


# ── Public API ────────────────────────────────────────────────────────────────────

def _process_binary_sync(image_bytes: bytes) -> bytes | None:
    """
    Decode → detect face → align → encode to JPEG.
    Returns JPEG bytes of the aligned face crop, or None if no face found.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        return None

    face_box = _detect_face(image)
    if face_box is None:
        logger.warning("process_binary_sync: no face detected")
        return None

    sface = _get_sface()
    try:
        aligned = sface.alignCrop(image, face_box)
    except Exception as e:
        logger.error("alignCrop error: %s", e)
        return None

    success, encoded = cv2.imencode(".jpg", aligned, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        return None
    return encoded.tobytes()


async def process_and_crop_binary(image_bytes: bytes) -> bytes | None:
    """Async wrapper – offloads CPU work to a thread pool."""
    return await asyncio.to_thread(_process_binary_sync, image_bytes)


def _compare_faces_sync(stored_bytes: bytes, capture_bytes: bytes) -> float:
    """
    Core synchronous comparison.
    Returns cosine similarity in [0, 1], or 0.0 on error.
    """
    def _decode(b):
        arr = np.frombuffer(b, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    stored_img  = _decode(stored_bytes)
    capture_img = _decode(capture_bytes)

    if stored_img is None or capture_img is None:
        return 0.0

    stored_box  = _detect_face(stored_img)
    capture_box = _detect_face(capture_img)

    if stored_box is None or capture_box is None:
        logger.warning(
            "compare_faces: face not found – stored=%s capture=%s",
            stored_box is None, capture_box is None,
        )
        return 0.0

    feat_stored  = _align_and_encode(stored_img, stored_box)
    feat_capture = _align_and_encode(capture_img, capture_box)

    if feat_stored is None or feat_capture is None:
        return 0.0

    sim = _cosine_similarity(feat_stored, feat_capture)
    logger.info("Face similarity (cosine): %.4f", sim)
    return sim


async def async_compare_faces(stored_bytes: bytes, capture_bytes: bytes) -> float:
    """Async wrapper – offloads CPU work to a thread pool."""
    return await asyncio.to_thread(_compare_faces_sync, stored_bytes, capture_bytes)


# ── Legacy shim (used by older code paths that pass a numpy array) ─────────────
def compare_faces_binary(stored_bytes: bytes, capture_array: np.ndarray) -> float:
    """Kept for backward-compatibility. Encodes the array and delegates."""
    success, buf = cv2.imencode(".jpg", capture_array)
    if not success:
        return 0.0
    return _compare_faces_sync(stored_bytes, buf.tobytes())
