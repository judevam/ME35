import cv2
import math
import numpy as np
from itertools import combinations

# --- Configuration ---
MARKER_REAL_WIDTH = 0.05  # Physical width of the marker in meters (e.g., 5 cm = 0.05)
FOCAL_LENGTH = 640.0      # Approximate focal length in pixels
MOVE_THRESHOLD = 2.0      # Minimum smoothed pixel speed to show movement
SMOOTHING = 0.25          # Lower = smoother/slower reaction (0.1 to 0.5)
ARROW_LENGTH = 60         # Fixed arrow length in pixels

cam = cv2.VideoCapture(0)
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())

prev_centers = {}
smooth_vectors = {}

while True:
    ret, frame = cam.read()
    if not ret:
        break

    h, w = frame.shape[:2]
    img_center_x = w / 2.0
    img_center_y = h / 2.0

    corners, ids, _ = detector.detectMarkers(frame)

    # Store visible markers in this frame: {marker_id: (px_center, (X, Y, Z))}
    visible_markers = {}

    if ids is not None:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        for i, c in enumerate(corners):
            marker_id = int(ids.flatten()[i])
            pts = c[0]

            # 1. Calculate Depth (Z) from Camera
            pixel_width = np.linalg.norm(pts[0] - pts[1])
            z_dist = (MARKER_REAL_WIDTH * FOCAL_LENGTH) / pixel_width if pixel_width > 0 else 0

            # 2. Calculate 2D Sub-pixel Center & 3D Coordinates (X, Y, Z)
            curr_center = np.mean(pts, axis=0)
            cx, cy = float(curr_center[0]), float(curr_center[1])

            X = ((cx - img_center_x) * z_dist) / FOCAL_LENGTH
            Y = ((cy - img_center_y) * z_dist) / FOCAL_LENGTH
            visible_markers[marker_id] = ((int(cx), int(cy)), (X, Y, z_dist))

            # 3. Calculate Smoothed Movement Direction
            direction = "Stationary"
            if marker_id in prev_centers:
                px, py = prev_centers[marker_id]
                raw_dx = cx - px
                raw_dy = cy - py

                prev_vx, prev_vy = smooth_vectors.get(marker_id, (0.0, 0.0))
                vx = SMOOTHING * raw_dx + (1.0 - SMOOTHING) * prev_vx
                vy = SMOOTHING * raw_dy + (1.0 - SMOOTHING) * prev_vy
                smooth_vectors[marker_id] = (vx, vy)

                speed = math.hypot(vx, vy)

                if speed > MOVE_THRESHOLD:
                    angle = math.degrees(math.atan2(vy, vx))
                    if abs(vx) > abs(vy):
                        direction = "Right" if vx > 0 else "Left"
                    else:
                        direction = "Down" if vy > 0 else "Up"
                    direction += f" ({angle:.0f} deg)"

                    ux = vx / speed
                    uy = vy / speed
                    start_pt = (int(cx), int(cy))
                    end_pt = (int(cx + ux * ARROW_LENGTH), int(cy + uy * ARROW_LENGTH))
                    cv2.arrowedLine(frame, start_pt, end_pt, (0, 255, 0), 3, tipLength=0.3)

            prev_centers[marker_id] = (cx, cy)

            # Label individual marker
            label = f"ID {marker_id} | Z: {z_dist:.2f}m | {direction}"
            cv2.putText(frame, label, (int(cx) - 60, int(cy) - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        # 4. Draw Lines & Distances Between All Pairs of Detected Markers
        for (id1, data1), (id2, data2) in combinations(visible_markers.items(), 2):
            pt1_2d, pos1_3d = data1
            pt2_2d, pos2_3d = data2

            # 3D Euclidean distance between the two markers
            pair_dist = math.dist(pos1_3d, pos2_3d)

            # Draw connecting line
            cv2.line(frame, pt1_2d, pt2_2d, (255, 0, 255), 2)

            # Place distance label at the midpoint of the line
            mid_x = (pt1_2d[0] + pt2_2d[0]) // 2
            mid_y = (pt1_2d[1] + pt2_2d[1]) // 2
            cv2.putText(frame, f"{pair_dist:.2f}m", (mid_x, mid_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

    cv2.imshow("aruco", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cam.release()
cv2.destroyAllWindows()
cv2.waitKey(1)
