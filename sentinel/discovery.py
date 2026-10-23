"""Offline-only clustering for discovering unhandled intents in consented samples.

DO NOT feed raw production conversations to this module. Its results are
hypotheses for human review, not authority for any online workflow.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from sentinel.intent import classify, normalize, redact_secrets

_STOPWORDS = {
    "من", "ما", "و", "را", "رو", "از", "به", "در", "با", "برای", "می", "کنم",
    "میخوام", "میخواهم", "باید", "که", "چی", "چطوری", "لطفا", "میشه",
    "منو", "my", "can", "you", "the", "please", "to", "how", "is",
}

def terms(sentence: str) -> frozenset[str]:
    cleaned, _ = redact_secrets(sentence)
    tokens = re.findall(r"[\w\u0600-\u06FF]{3,}", normalize(cleaned))
    return frozenset(t for t in tokens if t not in _STOPWORDS
                     and not t.startswith("redacted") and not re.fullmatch(r"\d+", t))

def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0

def discover_unknown_topics(
    examples: Iterable[str], *, threshold: float = 0.34, min_samples: int = 2,
    max_examples: int = 2000,
) -> dict:
    """Connected-component clustering over pre-redacted consented *unknown* examples.

    Clustering is deliberately offline and deterministic, avoiding a model that
    might accidentally classify private tokens or trigger unsupported actions.
    We output aggregate terms and counts only, never original text.
    """
    if not 0 < threshold <= 1 or not 2 <= min_samples <= max_examples <= 10000:
        raise ValueError("invalid offline-clustering configuration")
    vectors = []
    examined = 0
    skipped_sensitive = 0
    skipped_known = 0
    for sentence in examples:
        if examined >= max_examples:
            break
        examined += 1
        if not isinstance(sentence, str) or len(sentence) > 3000:
            continue
        _, has_secret = redact_secrets(sentence)
        if has_secret:
            skipped_sensitive += 1
            continue
        decision = classify(sentence)
        if decision.certainty != "unknown":
            skipped_known += 1
            continue
        vector = terms(sentence)
        if vector:
            vectors.append(vector)
    visited = set()
    components = []
    for i in range(len(vectors)):
        if i in visited:
            continue
        to_visit = [i]
        visited.add(i)
        group = []
        while to_visit:
            index = to_visit.pop()
            group.append(index)
            for j in range(len(vectors)):
                if j not in visited and similarity(vectors[index], vectors[j]) >= threshold:
                    visited.add(j)
                    to_visit.append(j)
        if len(group) >= min_samples:
            frequencies = Counter(token for j in group for token in vectors[j])
            components.append({
                "count": len(group),
                "top_terms": [token for token, _ in
                              sorted(frequencies.items(), key=lambda p: (-p[1], p[0]))[:6]],
                "decision": "human_review_only",
            })
    return {
        "sample_count": examined,
        "unhandled_count": len(vectors),
        "known_count": skipped_known,
        "skipped_sensitive": skipped_sensitive,
        "clusters": sorted(components, key=lambda c: (-c["count"], c["top_terms"])),
        "noise_count": len(vectors) - sum(c["count"] for c in components),
        "limitations": [
            "Only explicitly provided, consented offline examples; no user profiling.",
            "Tokens and clusters are hypotheses for review, not runtime intents.",
            "Connected components may overmerge similar short phrases.",
        ],
    }
