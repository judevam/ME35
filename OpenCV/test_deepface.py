import cv2
import os
import threading
import time
from datetime import datetime
from deepface import DeepFace

# Snapshots are saved in a "snapshots" folder next to this script
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ---- Settings you can tweak ----
ACTIONS = ['emotion', 'age', 'gender']  # remove 'age' and/or 'gender' for a big speedup
SCALE = 0.5                             # analyze a half-size copy of each frame (smaller = faster)
FRAME_W, FRAME_H = 640, 480             # webcam resolution

cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

if not cam.isOpened():
    print("Could not open webcam")
    raise SystemExit

latest_frame = None   # newest webcam frame, shared with the worker thread
results = []          # newest analysis results, shared with the main loop
lock = threading.Lock()
stop = threading.Event()


def analyze_loop():
    """Runs in the background: grabs the newest frame, analyzes it, stores the results."""
    global results
    while not stop.is_set():
        with lock:
            frame = None if latest_frame is None else latest_frame.copy()
        if frame is None:
            time.sleep(0.01)
            continue

        small = cv2.resize(frame, None, fx=SCALE, fy=SCALE)
        try:
            analysis = DeepFace.analyze(
                img_path=small,
                actions=ACTIONS,
                detector_backend='opencv',
                enforce_detection=False,
                silent=True
            )
        except Exception as e:
            print("DeepFace error:", e)
            analysis = []

        faces = []
        sh, sw = small.shape[:2]
        for face in analysis:
            r = face.get('region', {})
            x, y, w, h = r.get('x', 0), r.get('y', 0), r.get('w', 0), r.get('h', 0)

            # Skip "no face found" results (empty box or the whole image)
            if w == 0 or h == 0 or (w >= sw and h >= sh):
                continue

            parts = []
            if 'emotion' in ACTIONS:
                parts.append(face.get('dominant_emotion', '?').capitalize())
            if 'gender' in ACTIONS:
                parts.append(face.get('dominant_gender', '?'))
            if 'age' in ACTIONS:
                parts.append(f"~{face.get('age', '?')}")

            # Scale the box back up to full-size frame coordinates
            box = (int(x / SCALE), int(y / SCALE), int(w / SCALE), int(h / SCALE))
            faces.append((box, " | ".join(parts)))

        with lock:
            results = faces


worker = threading.Thread(target=analyze_loop, daemon=True)
worker.start()

print("Loading models... the first result can take 10-30 seconds.")
print("Press 's' to take a snapshot, 'q' to quit (click the video window first).")

saved_message_until = 0  # time until the "Saved!" message disappears

while True:
    ret, frame = cam.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)  # mirror view

    with lock:
        latest_frame = frame
        current = list(results)

    display = frame.copy()
    for (x, y, w, h), label in current:
        cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(display, label, (x, max(y - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break

    if key == ord('s'):
        # Save the frame with the boxes and labels drawn on it
        filename = datetime.now().strftime("snapshot_%Y-%m-%d_%H-%M-%S.png")
        path = os.path.join(SNAPSHOT_DIR, filename)
        cv2.imwrite(path, display)
        print("Saved", path)
        saved_message_until = time.time() + 1.5

    # Show a short "Saved!" message on screen (not included in the snapshot itself)
    shown = display
    if time.time() < saved_message_until:
        shown = display.copy()
        cv2.putText(shown, "Saved!", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

    cv2.imshow("DeepFace Webcam Test", shown)

stop.set()
worker.join(timeout=2)
cam.release()
cv2.destroyAllWindows()
cv2.waitKey(1)