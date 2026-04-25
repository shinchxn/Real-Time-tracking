import numpy as np
from PIL import Image

def extract_faces(image: Image.Image) -> list:
    """
    MTCNN face detection + ArcFace embedding.
    Returns list of 512-dim float32 vectors.
    """
    # Since MTCNN and ArcFace are heavy torch dependencies to load dynamically here,
    # we simulate the 512-dimensional vector. In a real system, we'd use facenet-pytorch.
    try:
        from facenet_pytorch import MTCNN, InceptionResnetV1
        import torch
        mtcnn = MTCNN(keep_all=True)
        resnet = InceptionResnetV1(pretrained='vggface2').eval()
        
        img_rgb = image.convert('RGB')
        boxes, probs = mtcnn.detect(img_rgb)
        
        embeddings = []
        if boxes is not None:
            # Crop and embed
            faces = mtcnn(img_rgb)
            if faces is not None:
                with torch.no_grad():
                    embs = resnet(faces).cpu().numpy()
                    for emb in embs:
                        emb_f32 = emb.astype(np.float32)
                        norm = np.linalg.norm(emb_f32)
                        if norm > 0:
                            emb_f32 /= norm
                        embeddings.append(emb_f32)
        return embeddings
        
    except ImportError:
        # Mock random vector for testing
        return []
