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
_LIVENESS_PATH = os.path.join(_ASSETS_DIR, "MiniFASNetV2.onnx")

# Validate model files exist
if not os.path.exists(_YUNET_PATH):
    raise FileNotFoundError(f"YuNet model not found at: {_YUNET_PATH}")
if not os.path.exists(_SFACE_PATH):
    raise FileNotFoundError(f"SFace model not found at: {_SFACE_PATH}")
if not os.path.exists(_LIVENESS_PATH):
    raise FileNotFoundError(f"Liveness model not found at: {_LIVENESS_PATH}")

# ── Custom Exceptions ───────────────────────────────────────────────────────────
class LivenessError(Exception):
    """Raised when an anti-spoofing check fails (detected photo/screen)."""
    pass

# ── Lazy-loaded singleton models (thread-safe creation at first use) ─────────────
_yunet_detector = None
_sface_recognizer = None
_liveness_net = None

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

def _get_liveness_net():
    global _liveness_net
    if _liveness_net is None:
        _liveness_net = cv2.dnn.readNetFromONNX(_LIVENESS_PATH)
    return _liveness_net


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


def _check_liveness(image: np.ndarray, face_box) -> bool:
    """
    Perform anti-spoofing checks (texture + DL model).
    Returns True if live, raises LivenessError if fake.
    """
    # ── 1. Laplacian Variance (Blur Check) ──
    # Photos of screens or printouts are often slightly blurry or have moire patterns.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Use the raw face box for blur check
    x_b, y_b, w_b, h_b = face_box[0][0:4].astype(int)
    ih, iw = image.shape[:2]
    # Clip to image bounds
    xb_min, yb_min = max(0, x_b), max(0, y_b)
    xb_max, yb_max = min(x_b + w_b, iw), min(y_b + h_b, ih)
    roi_gray = gray[yb_min:yb_max, xb_min:xb_max]
    
    if roi_gray.size > 0:
        blur_score = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        logger.info("Liveness: Laplacian Variance = %.2f", blur_score)
        # Lowered threshold to 5 to avoid false positives with softer cameras or low light.
        if blur_score < 5:
            logger.warning("Liveness: Laplacian check failed (score: %.2f)", blur_score)
            raise LivenessError("Kualitas foto rendah atau terdeteksi layar (Blur)")

    # ── 2. MiniFASNetV2 (Deep Learning Anti-Spoofing) ──
    try:
        # Scale 2.7 crop as expected by the model
        cx, cy = x_b + w_b / 2, y_b + h_b / 2
        new_size = max(w_b, h_b) * 2.7
        x1 = int(cx - new_size / 2)
        y1 = int(cy - new_size / 2)
        x2 = int(x1 + new_size)
        y2 = int(y1 + new_size)
        
        # Crop and pad with black if out of bounds
        xi1, yi1 = max(0, x1), max(0, y1)
        xi2, yi2 = min(iw, x2), min(ih, y2)
        
        face_img = image[yi1:yi2, xi1:xi2]
        if face_img.size == 0:
            return True

        # If crop was smaller than new_size, pad it
        if xi2 - xi1 < x2 - x1 or yi2 - yi1 < y2 - y1:
            pad_top = max(0, yi1 - y1)
            pad_bottom = max(0, y2 - yi2)
            pad_left = max(0, xi1 - x1)
            pad_right = max(0, x2 - xi2)
            face_img = cv2.copyMakeBorder(face_img, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_CONSTANT, value=[0,0,0])

        # Resize to 80x80 as expected
        face_img = cv2.resize(face_img, (80, 80))
        # model expects BGR, [0, 255], float32, NCHW
        face_img = face_img.astype(np.float32)
        
        # Convert to NCHW format (1, 3, 80, 80)
        blob = np.transpose(face_img, (2, 0, 1)) # HWC -> CHW
        blob = np.expand_dims(blob, axis=0)      # CHW -> NCHW
        
        net = _get_liveness_net()
        net.setInput(blob)
        preds = net.forward() # Output shape (1, 3)
        
        # Simple softmax to log probabilities
        probs = np.exp(preds[0]) / np.sum(np.exp(preds[0]))
        label = np.argmax(preds[0])
        score = probs[label]
        
        logger.info("Liveness: DL Model result = %d (prob: %.4f)", label, score)
        
        # In this model (yakhyo/Silent-Face-Anti-Spoofing), 1 is REAL.
        if label != 1:
            logger.warning("Liveness: DL Model detected SPOOF (label: %d, prob: %.4f)", label, score)
            raise LivenessError("Kecurangan terdeteksi (Anti-Spoofing)")
            
    except LivenessError:
        raise
    except Exception as e:
        logger.error("Liveness check error: %s", e)
        return True

    return True


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

    # ── Anti-Spoofing Check (LIVENESS) ──
    # Only check liveness on the captured image, not the stored one.
    _check_liveness(capture_img, capture_box)

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
