import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. Initialize the HandLandmarker in VIDEO mode
base_options = python.BaseOptions(model_asset_path="hand_landmarker.task")
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=2,
    min_hand_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
detector = vision.HandLandmarker.create_from_options(options)

# Connections between the 21 hand landmarks
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (9, 13), (13, 14), (14, 15), (15, 16), # Ring
    (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
    (0, 17)                                # Palm base
]

cam = cv2.VideoCapture(0)
start_time = time.time()

while True:
    ret, frame = cam.read()
    if not ret:
        break

    # Mirror the webcam feed for natural movement
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    # Convert BGR (OpenCV) to RGB (MediaPipe)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Calculate monotonically increasing timestamp in milliseconds
    timestamp_ms = int((time.time() - start_time) * 1000)

    # Run hand landmark detection
    result = detector.detect_for_video(mp_image, timestamp_ms)

    if result.hand_landmarks:
        for idx, hand_landmarks in enumerate(result.hand_landmarks):
            # Convert normalized (0.0 - 1.0) coordinates to pixel coordinates
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]

            # Draw skeleton lines
            for start_idx, end_idx in HAND_CONNECTIONS:
                cv2.line(frame, pts[start_idx], pts[end_idx], (0, 255, 0), 2)

            # Draw joint dots
            for cx, cy in pts:
                cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

            # Label Left/Right hand near the wrist (landmark 0)
            if result.handedness:
                hand_label = result.handedness[idx][0].category_name
                cv2.putText(frame, hand_label, (pts[0][0] - 20, pts[0][1] + 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    cv2.imshow("Hand Pose Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

detector.close()
cam.release()
cv2.destroyAllWindows()
cv2.waitKey(1)
