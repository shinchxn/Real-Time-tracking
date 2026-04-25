import cv2
import numpy as np

def detect_scenes(video_path: str, threshold=30.0) -> list:
    """
    Identifies scene cuts in a video based on absolute difference of hist.
    Returns list of frame indices where a scene cut occurred.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
        
    scene_cuts = []
    ret, prev_frame = cap.read()
    if not ret:
        return scene_cuts
        
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    frame_idx = 1
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray, prev_gray)
        mean_diff = np.mean(diff)
        
        if mean_diff > threshold:
            scene_cuts.append(frame_idx)
            
        prev_gray = gray
        frame_idx += 1
        
    cap.release()
    return scene_cuts
