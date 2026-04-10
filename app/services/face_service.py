import cv2
import numpy as np
import asyncio

# Load OpenCV Haar Cascade face detector
_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

def detect_and_crop_face(image: np.ndarray) -> np.ndarray | None:
    """
    Detect the largest face in an image and return a cropped, normalized version.
    Returns None if no face is detected.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80),
    )
    if len(faces) == 0:
        return None

    # Use the largest detected face
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    # Add small padding
    pad = int(min(w, h) * 0.15)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(image.shape[1], x + w + pad)
    y2 = min(image.shape[0], y + h + pad)

    face_crop = image[y1:y2, x1:x2]
    # Resize to a fixed size for consistent comparison
    face_crop = cv2.resize(face_crop, (200, 200))
    return face_crop


def compare_faces_binary(stored_bytes: bytes, capture_array: np.ndarray) -> float:
    """
    Compare a stored face image (binary) with a captured face using histogram correlation.
    """
    # Decode stored binary image
    nparr = np.frombuffer(stored_bytes, np.uint8)
    stored_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if stored_img is None:
        return 0.0

    # These are already cropped if coming from the DB, but applying logic again for safety
    stored_face = detect_and_crop_face(stored_img)
    capture_face = detect_and_crop_face(capture_array)

    if stored_face is None or capture_face is None:
        return 0.0

    # Convert both to HSV for color-independent comparison
    stored_hsv = cv2.cvtColor(stored_face, cv2.COLOR_BGR2HSV)
    capture_hsv = cv2.cvtColor(capture_face, cv2.COLOR_BGR2HSV)

    # Calculate histogram for each channel and compare
    similarity_scores = []
    for channel in range(3):
        hist_stored = cv2.calcHist([stored_hsv], [channel], None, [64], [0, 256])
        hist_capture = cv2.calcHist([capture_hsv], [channel], None, [64], [0, 256])
        cv2.normalize(hist_stored, hist_stored)
        cv2.normalize(hist_capture, hist_capture)
        score = cv2.compareHist(hist_stored, hist_capture, cv2.HISTCMP_CORREL)
        similarity_scores.append(score)

    return float(np.mean(similarity_scores))


async def process_and_crop_binary(image_bytes: bytes) -> bytes | None:
    """
    Offload face processing to a thread to avoid blocking the event loop.
    Returns JPEG encoded bytes if face is found, else None.
    """
    def _process():
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            return None
        
        face_crop = detect_and_crop_face(image)
        if face_crop is None:
            return None
            
        success, encoded_image = cv2.imencode('.jpg', face_crop)
        if success:
            return encoded_image.tobytes()
        return None

    return await asyncio.to_thread(_process)


async def async_compare_faces(stored_bytes: bytes, capture_bytes: bytes) -> float:
    """
    Offload face comparison to a thread.
    """
    def _process():
        capture_nparr = np.frombuffer(capture_bytes, np.uint8)
        capture_img = cv2.imdecode(capture_nparr, cv2.IMREAD_COLOR)
        if capture_img is None:
            return 0.0
        return compare_faces_binary(stored_bytes, capture_img)

    return await asyncio.to_thread(_process)
