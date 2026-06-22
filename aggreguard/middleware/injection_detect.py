"""Component 2 — prompt-injection detection (wraps off-the-shelf detectors).

Baseline detectors only — this is not the project's novelty (plan §4 C2). Two
implementations behind a common interface:

  - ``HFInjectionDetector``: wraps a HuggingFace text-classification model
    (default: ProtectAI/deberta-v3-base-prompt-injection-v2; Meta Prompt-Guard-86M
    also works). transformers/torch are imported lazily and the model is downloaded
    on first use, so importing this module is cheap and dependency-free.
  - ``KeywordInjectionDetector``: a tiny zero-dependency heuristic baseline so the
    pipeline and tests run without pulling a model.

Mount either at untrusted-data entry points (WEB / TOOL provenance).
"""

from __future__ import annotations

import re
from typing import Protocol

# Default HF model id (override via HFInjectionDetector(model_id=...)).
DEFAULT_MODEL_ID = "ProtectAI/deberta-v3-base-prompt-injection-v2"

# Phrases commonly seen in indirect prompt-injection payloads. Coarse on purpose —
# this is a stand-in baseline, not the real detector.
_INJECTION_PATTERNS = [
    r"ignore (all|any|the)? ?(previous|prior|above) instructions",
    r"disregard (the )?(system|previous|above)",
    r"you are now",
    r"new instructions?:",
    r"important instructions?",
    r"do not tell the user",
    r"send (an )?email to",
    r"forward .* to",
    r"\bsystem prompt\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


class InjectionDetector(Protocol):
    """Common interface: return injection probability in [0, 1]."""

    def detect(self, text: str) -> float: ...


class KeywordInjectionDetector:
    """Zero-dependency heuristic baseline. Score = saturating count of pattern hits."""

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        hits = sum(1 for pat in _COMPILED if pat.search(text))
        return min(1.0, hits / 2.0)  # 2+ distinct hits saturates to 1.0

    def is_injection(self, text: str) -> bool:
        return self.detect(text) >= self.threshold


class HFInjectionDetector:
    """Wraps a HuggingFace prompt-injection classifier. Lazy-loads the model."""

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, threshold: float = 0.5):
        self.model_id = model_id
        self.threshold = threshold
        self._pipe = None

    def _ensure_loaded(self):
        if self._pipe is not None:
            return
        try:
            from transformers import pipeline
        except ImportError as e:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "HFInjectionDetector needs the 'detectors' extra: "
                "pip install -e '.[detectors]'"
            ) from e
        self._pipe = pipeline("text-classification", model=self.model_id, truncation=True)

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        self._ensure_loaded()
        result = self._pipe(text)[0]
        label = str(result["label"]).upper()
        score = float(result["score"])
        # Models label the injection class as INJECTION / LABEL_1 / UNSAFE etc.
        positive = label in {"INJECTION", "LABEL_1", "UNSAFE", "JAILBREAK"}
        return score if positive else 1.0 - score

    def is_injection(self, text: str) -> bool:
        return self.detect(text) >= self.threshold


def detect_injection(text: str, detector: InjectionDetector | None = None) -> float:
    """Module-level convenience. Defaults to the zero-dependency keyword baseline."""
    detector = detector or KeywordInjectionDetector()
    return detector.detect(text)
