import os
import time
from typing import List, Tuple, Any
from huggingface_hub import InferenceClient
from app.observability import log_telemetry, track_hf_call

class HuggingFaceAdapter:
    """
    Adapter for interacting with HuggingFace API for embeddings and cross-encoder reranking.
    Handles retries, logging, and error mapping.
    """
    def __init__(self, model_name: str):
        self.model_name = model_name
        token = os.getenv("HF_TOKEN")
        self.client = InferenceClient(model=model_name, token=token)
        log_telemetry("INFO", f"HuggingFaceAdapter initialized for model: {self.model_name}")

    def feature_extraction(self, texts: List[str]) -> Any:
        """Extracts dense embeddings from a list of texts."""
        log_telemetry("INFO", f"HuggingFaceAdapter: Extracting features for {len(texts)} texts using {self.model_name}")
        track_hf_call()
        for attempt in range(4):
            try:
                res = self.client.feature_extraction(texts)
                log_telemetry("INFO", "HuggingFaceAdapter: Feature extraction successful.")
                return res
            except Exception as e:
                log_telemetry("WARNING", f"HuggingFaceAdapter: Attempt {attempt + 1} failed for feature extraction - {e}")
                if attempt == 3:
                    log_telemetry("ERROR", "HuggingFaceAdapter: All attempts for feature extraction failed.")
                    raise
                time.sleep(1)

    def text_classification(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """Performs cross-encoder text classification (reranking) on query-document pairs."""
        log_telemetry("INFO", f"HuggingFaceAdapter: Classifying {len(pairs)} text pairs using {self.model_name}")
        track_hf_call()
        scores = []
        for q, text in pairs:
            for attempt in range(4):
                try:
                    res = self.client.text_classification(f"{q} [SEP] {text}")
                    if isinstance(res, list) and len(res) > 0:
                        score = res[0].score if hasattr(res[0], "score") else res[0].get("score", 0.0)
                        scores.append(score)
                    else:
                        scores.append(0.0)
                    break
                except Exception as e:
                    if attempt == 3:
                        log_telemetry("ERROR", f"HuggingFaceAdapter: Classification failed for pair - {e}")
                        scores.append(0.0)
                    time.sleep(1)
        log_telemetry("INFO", f"HuggingFaceAdapter: Classification complete for {len(pairs)} pairs.")
        return scores
