import hashlib
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.engine import AnalysisEngine


class FakeTokenizer:
    def __call__(self, text, **kwargs):
        return {"offset_mapping": [match.span() for match in re.finditer(r"\S+", text)]}

    def encode(self, text, add_special_tokens=False):
        return text.split() + (["[CLS]", "[SEP]"] if add_special_tokens else [])

    def decode(self, tokens, **kwargs):
        return " ".join(tokens)


class FakeModel:
    """Deterministic word hashing, not an imitation of model quality."""
    tokenizer = FakeTokenizer()

    def encode(self, texts, normalize_embeddings=True, **kwargs):
        vectors = []
        for text in texts:
            vector = np.zeros(384)
            for word in re.findall(r"\w+", text.lower()):
                index = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % 384
                vector[index] += 1
            norm = np.linalg.norm(vector)
            vectors.append(vector / norm if norm else vector)
        return np.array(vectors)


@pytest.fixture
def engine():
    return AnalysisEngine(model_factory=FakeModel)


@pytest.fixture
def client(tmp_path, engine):
    app = create_app(Settings(database_path=tmp_path / "test.sqlite3", password="", production=False), engine)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as test_client:
        yield test_client
