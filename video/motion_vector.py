import cv2
import numpy as np

def extract_motion_vectors(video_path: str, max_frames=60) -> np.ndarray:
    """
    Farneback optical flow fingerprint across video frames.
    """
    cap = cv2.VideoCapture(video_path)
    ret, frame1 = cap.read()
    if not ret:
        return np.zeros(128, dtype=np.float32)
        
    prvs = cv2.cvtColor(cv2.resize(frame1, (128, 128)), cv2.COLOR_BGR2GRAY)
    
    flow_magnitudes = []
    frames_processed = 0
    
    while frames_processed < max_frames:
        ret, frame2 = cap.read()
        if not ret:
            break
            
        next_gray = cv2.cvtColor(cv2.resize(frame2, (128, 128)), cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(prvs, next_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        
        flow_magnitudes.append(np.mean(mag))
        prvs = next_gray
        frames_processed += 1
        
    cap.release()
    
    # 128-dim feature vector of motion distribution
    hist, _ = np.histogram(flow_magnitudes, bins=128, range=(0.0, 10.0))
    hist_float = hist.astype(np.float32)
    norm = np.linalg.norm(hist_float)
    if norm > 0:
        hist_float /= norm
        
    return hist_float
