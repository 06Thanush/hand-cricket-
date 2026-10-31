"""
gesture.py  -  get_number()

KEY FIX: Detector and camera are loaded ONCE at startup (module level),
so every SPACE press opens the camera window INSTANTLY with zero delay.
Falls back to keyboard if camera/mediapipe unavailable.
"""

import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

# ── Landmark indices ──────────────────────────────────────────────────────────
THUMB_TIP   = 4
THUMB_IP    = 3
FINGER_TIPS = [8, 12, 16, 20]
FINGER_PIPS = [6, 10, 14, 18]

CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# ── Try importing libs ────────────────────────────────────────────────────────
try:
    import cv2
    import numpy as np
    import mediapipe as mp
    from mediapipe.tasks.python import vision as mp_vision
    from mediapipe.tasks.python.core import base_options as mp_base
    _LIBS_OK = True
except ImportError:
    _LIBS_OK = False


# ── Download model if needed ──────────────────────────────────────────────────
def _download_model() -> bool:
    if os.path.exists(MODEL_PATH):
        return True
    print("[gesture] Downloading hand landmark model (~8 MB) - only once...")
    try:
        import urllib.request
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[gesture] Model downloaded.")
        return True
    except Exception as e:
        print(f"[gesture] Download failed: {e}")
        return False


# ── Preload detector and camera at module import (runs once at startup) ───────
_detector = None
_cap      = None
_CAMERA_OK = False

def _preload():
    """
    Called once when this module is imported.
    Loads the MediaPipe model and opens the camera in advance
    so get_number() is instant when the player presses SPACE.
    """
    global _detector, _cap, _CAMERA_OK

    if not _LIBS_OK:
        print("[gesture] MediaPipe/OpenCV not installed - using keyboard mode.")
        return

    if not _download_model():
        print("[gesture] Model unavailable - using keyboard mode.")
        return

    # Load detector
    try:
        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_base.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.3,
            min_hand_presence_confidence=0.3,
            min_tracking_confidence=0.3,
        )
        _detector = mp_vision.HandLandmarker.create_from_options(options)
        print("[gesture] Hand detector loaded.")
    except Exception as e:
        print(f"[gesture] Detector failed to load: {e}")
        return

    # Open camera
    try:
        _cap = cv2.VideoCapture(0)
        if not _cap.isOpened():
            raise RuntimeError("Camera index 0 not available")
        _cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        _cap.set(cv2.CAP_PROP_FPS, 30)
        # Warm up - read a few frames so first real read is instant
        for _ in range(5):
            _cap.read()
        print("[gesture] Camera ready.")
        _CAMERA_OK = True
    except Exception as e:
        print(f"[gesture] Camera failed: {e}")
        if _detector:
            _detector.close()
            _detector = None


# ── Helper functions ──────────────────────────────────────────────────────────
def _count_fingers(landmarks, is_right_hand: bool) -> int:
    """
    Count raised fingers (1-6).
    After cv2.flip(frame,1), MediaPipe handedness is mirrored - we swap it.
    """
    actual_right = not is_right_hand   # fix mirror flip

    count = 0

    # Thumb
    tip = landmarks[THUMB_TIP]
    ip  = landmarks[THUMB_IP]
    if actual_right:
        if tip.x < ip.x:
            count += 1
    else:
        if tip.x > ip.x:
            count += 1

    # Four fingers: tip above PIP = extended
    for tip_id, pip_id in zip(FINGER_TIPS, FINGER_PIPS):
        if landmarks[tip_id].y < landmarks[pip_id].y:
            count += 1

    return max(1, min(count, 6))


def _draw_skeleton(frame, landmarks, w: int, h: int) -> None:
    pts     = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    tip_set = set(FINGER_TIPS + [THUMB_TIP])
    for a, b in CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], (0, 200, 100), 2)
    for i, pt in enumerate(pts):
        color  = (0, 255, 180) if i in tip_set else (255, 255, 255)
        radius = 6              if i in tip_set else 3
        cv2.circle(frame, pt, radius, color, -1)


# ── Main camera capture (instant because detector+cap already loaded) ─────────
def _get_number_camera() -> int:
    global _cap

    if not _CAMERA_OK or _detector is None or _cap is None:
        raise RuntimeError("Camera not ready")

    # Re-open if camera was released
    if not _cap.isOpened():
        _cap = cv2.VideoCapture(0)
        _cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        _cap.set(cv2.CAP_PROP_FPS, 30)
        if not _cap.isOpened():
            raise RuntimeError("Camera lost")

    CONFIRM_FRAMES = 12
    stable_num   = None
    stable_count = 0
    result_num   = None

    while True:
        ret, frame = _cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, 1)
        h, w  = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb, dtype=np.uint8)

        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection = _detector.detect(mp_image)

        if detection.hand_landmarks:
            landmarks  = detection.hand_landmarks[0]
            handedness = detection.handedness[0][0].category_name
            is_right   = (handedness == "Right")

            _draw_skeleton(frame, landmarks, w, h)
            detected_num = _count_fingers(landmarks, is_right)

            if detected_num == stable_num:
                stable_count += 1
            else:
                stable_num   = detected_num
                stable_count = 1

            # Progress bar
            bar_fill = int((stable_count / CONFIRM_FRAMES) * 220)
            cv2.rectangle(frame, (w//2-110, h-55), (w//2+110, h-30), (40,40,40), -1)
            cv2.rectangle(frame, (w//2-110, h-55),
                          (w//2-110+bar_fill, h-30), (0,220,100), -1)
            cv2.putText(frame, f"Hold still!  Fingers: {detected_num}",
                        (w//2-150, h-60), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255,255,255), 2)

            # Big number top-right
            cv2.putText(frame, str(detected_num),
                        (w-100, 120), cv2.FONT_HERSHEY_SIMPLEX,
                        4, (0,255,100), 8)

            if stable_count >= CONFIRM_FRAMES:
                result_num = detected_num
                # Green flash
                overlay    = np.zeros_like(frame)
                overlay[:] = (0, 200, 0)
                frame = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)
                cv2.putText(frame, f"CONFIRMED: {result_num}",
                            (w//2-180, h//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255,255,255), 4)
                cv2.imshow("Hand Cricket - Gesture Input", frame)
                cv2.waitKey(350)
                break

        else:
            stable_num   = None
            stable_count = 0
            cv2.putText(frame,
                        "No hand detected - show hand in good light",
                        (w//2-240, h-45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0,100,255), 2)

        # Top bar
        cv2.rectangle(frame, (0,0), (w,48), (0,0,0), -1)
        cv2.putText(frame,
                    "Show 1-6 fingers | Hold steady | Q = keyboard mode",
                    (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 2)

        cv2.imshow("Hand Cricket - Gesture Input", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break

    cv2.destroyAllWindows()

    if result_num is None:
        raise RuntimeError("No confirmed gesture")
    return result_num


# ── Keyboard fallback ─────────────────────────────────────────────────────────
def _get_number_keyboard() -> int:
    import pygame
    screen   = pygame.display.get_surface()
    font_big = pygame.font.SysFont(None, 70)
    font_sm  = pygame.font.SysFont(None, 34)

    while True:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        screen.blit(overlay, (0, 0))
        title = font_big.render("Press  1 - 6  to play", True, (255, 255, 100))
        note  = font_sm.render("(camera not available - keyboard mode)", True, (160,160,160))
        screen.blit(title, (screen.get_width()//2 - title.get_width()//2, 230))
        screen.blit(note,  (screen.get_width()//2 - note.get_width()//2,  310))
        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3,
                                 pygame.K_4, pygame.K_5, pygame.K_6):
                    return int(event.unicode)


# ── Public API ────────────────────────────────────────────────────────────────
def get_number() -> int:
    """
    Return confirmed integer 1-6 from hand gesture.
    Camera opens INSTANTLY because detector was preloaded at startup.
    """
    if _CAMERA_OK:
        try:
            return _get_number_camera()
        except RuntimeError as e:
            print(f"[gesture] Camera failed ({e}), using keyboard.")
    return _get_number_keyboard()


def cleanup():
    """Call this when the game exits to release camera and detector."""
    global _cap, _detector
    if _cap and _cap.isOpened():
        _cap.release()
    if _detector:
        _detector.close()
    cv2.destroyAllWindows()
    print("[gesture] Camera and detector released.")


# ── Preload immediately when module is imported ───────────────────────────────
print("[gesture] Loading camera and hand detector at startup...")
_preload()
print("[gesture] Ready! Camera will open instantly when you press SPACE.")
