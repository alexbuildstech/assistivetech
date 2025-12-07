import cv2
import os

# Fix Qt plugin issue
os.environ['QT_QPA_PLATFORM'] = 'xcb'

print("🎥 Starting glasses camera feed...")
print("Press 'q' to quit")

cap = cv2.VideoCapture(2)

if not cap.isOpened():
    print("❌ Cannot open camera index 2. Trying index 0...")
    cap = cv2.VideoCapture(0)

# Set resolution
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ No webcam feed. Check camera connection.")
        break

    # Get frame dimensions
    h, w, _ = frame.shape
    
    # Take right half (glasses setup - camera on right side)
    right_half = frame[:, w // 2:]
    
    # Rotate 90 degrees clockwise (camera is tilted on glasses)
    rotated = cv2.rotate(right_half, cv2.ROTATE_90_CLOCKWISE)
    
    # Show processed live feed
    cv2.imshow("Glasses Feed (Live)", rotated)

    # Quit on 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("✅ Camera feed stopped")
