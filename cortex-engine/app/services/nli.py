import re

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class NLIService:
    """
    DeBERTa-v3-base NLI via ONNX Runtime.
    Classifies (premise, hypothesis) pairs into:
      entailment, neutral, contradiction
    """

    def __init__(self, model_dir: str):
        """
        model_dir should contain:
          - model.onnx (the ONNX model)
          - tokenizer.json (HuggingFace fast tokenizer)
        """
        self.session = ort.InferenceSession(
            f"{model_dir}/model.onnx",
            providers=["CPUExecutionProvider"],
        )
        self.tokenizer = Tokenizer.from_file(f"{model_dir}/tokenizer.json")
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.tokenizer.enable_truncation(max_length=512)
        # Label order from cross-encoder/nli-deberta-v3-base config.json
        self.labels = ["contradiction", "entailment", "neutral"]

        # Detect which inputs the ONNX model expects
        self._input_names = [inp.name for inp in self.session.get_inputs()]

    def predict(self, premise: str, hypothesis: str) -> dict:
        """
        Returns {"entailment": 0.92, "neutral": 0.05, "contradiction": 0.03}
        """
        encoded = self.tokenizer.encode(premise, hypothesis)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        feeds = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._input_names:
            token_type_ids = np.array([encoded.type_ids], dtype=np.int64)
            feeds["token_type_ids"] = token_type_ids

        outputs = self.session.run(None, feeds)

        logits = outputs[0][0]
        probs = self._softmax(logits)
        return {label: float(prob) for label, prob in zip(self.labels, probs)}

    def predict_batch(self, pairs: list[tuple[str, str]]) -> list[dict]:
        """Batch predict for efficiency."""
        results = []
        for premise, hypothesis in pairs:
            results.append(self.predict(premise, hypothesis))
        return results

    @staticmethod
    def _softmax(x):
        e = np.exp(x - np.max(x))
        return e / e.sum()


def check_nli(
    claim: str,
    sources: list[str],
    nli_service: NLIService,
    threshold: float = 0.7,
) -> tuple[bool, float, str | None]:
    """
    Check if any source sentence entails the claim.

    Strategy:
      1. Split each source into sentences
      2. For each sentence, run NLI(sentence, claim)
      3. If any sentence has entailment > threshold, GROUNDED
      4. Otherwise, UNSUPPORTED

    Returns: (grounded, confidence, best_source_sentence)
    """
    best_score = 0.0
    best_sentence = None

    for source in sources:
        sentences = re.split(r"[.!?]+", source)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        for sentence in sentences:
            result = nli_service.predict(sentence, claim)

            if result["entailment"] > best_score:
                best_score = result["entailment"]
                best_sentence = sentence

    grounded = best_score >= threshold
    return grounded, best_score, best_sentence if grounded else None
