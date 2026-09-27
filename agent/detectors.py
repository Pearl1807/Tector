"""The two ways the watcher can run Tector's detector.

LocalDetector (default) runs the model on this computer: about 2 s per check, works offline, and
pictures never leave the device. SpaceDetector sends crops to the Hugging Face Space instead
(about 4-7 s per check, needs internet) for computers without the model installed.
Both use the same model and trained weights as the web app, so they give the same scores.
"""
import os

import numpy as np

CLIP_MODEL = "openai/clip-vit-large-patch14"
HEAD_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tector_head.npz")


class LocalDetector:
    name = "this computer"

    def __init__(self):
        import torch  # imported here so Space mode works without torch installed
        from transformers import CLIPImageProcessor, CLIPVisionModel
        from transformers.utils import logging as hf_logging

        hf_logging.set_verbosity_error()  # hide the harmless "unused text weights" report
        hf_logging.disable_progress_bar()
        # Leave two cores for the rest of the computer; measured fastest on an 8-core laptop (2.0 s vs 2.5 s)
        torch.set_num_threads(max(1, (os.cpu_count() or 4) - 2))
        self.torch = torch
        self.processor = CLIPImageProcessor.from_pretrained(CLIP_MODEL)
        self.model = CLIPVisionModel.from_pretrained(CLIP_MODEL).eval()
        head = np.load(HEAD_PATH)
        self.coef, self.intercept = head["coef"], float(head["intercept"])

    def probs(self, crops, tmp_dir):
        with self.torch.inference_mode():
            feats = self.model(**self.processor(images=crops, return_tensors="pt")).pooler_output.numpy()
        feats /= np.linalg.norm(feats, axis=1, keepdims=True)
        return [float(p) for p in 1 / (1 + np.exp(-(feats @ self.coef + self.intercept)))]

    def reconnect(self):
        pass


class SpaceDetector:
    def __init__(self, space, client):
        self.name, self.space, self.client = space, space, client

    def probs(self, crops, tmp_dir):
        from gradio_client import handle_file

        paths = []
        for i, crop in enumerate(crops):
            path = os.path.join(tmp_dir, f"tector_region_{i}.jpg")
            crop.save(path, quality=90)
            paths.append(handle_file(path))
        return self.client.predict(paths, api_name="/detect_batch")["probs"]

    def reconnect(self):
        """A restarted Space can invalidate the old session, so try a fresh connection."""
        from gradio_client import Client

        try:
            self.client = Client(self.space, verbose=False)
        except Exception:
            pass
