from types import SimpleNamespace

import pytest

from agentic_rag import config
from agentic_rag.rag import embeddings


class FakeModels:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.calls: list[tuple[list[str], str]] = []

    def embed_content(self, *, model, contents, config):
        self.calls.append((contents, config.task_type))
        vectors = [SimpleNamespace(values=[0.1] * self.dim) for _ in contents]
        return SimpleNamespace(embeddings=vectors)


@pytest.fixture
def fake_client(monkeypatch):
    def install(dim: int = config.EMBEDDING_DIM) -> FakeModels:
        models = FakeModels(dim)
        monkeypatch.setattr(embeddings, "get_client", lambda: SimpleNamespace(models=models))
        monkeypatch.setattr(embeddings, "_limiter", embeddings.RateLimiter(1000, 10**9))
        return models

    return install


def test_embed_documents_batches_and_uses_document_task(fake_client) -> None:
    models = fake_client()
    texts = [f"testo {i}" for i in range(embeddings.BATCH_SIZE + 5)]
    vectors = embeddings.embed_documents(texts)
    assert len(vectors) == len(texts)
    assert [len(c) for c, _ in models.calls] == [embeddings.BATCH_SIZE, 5]
    assert {t for _, t in models.calls} == {"RETRIEVAL_DOCUMENT"}


def test_embed_query_uses_query_task(fake_client) -> None:
    models = fake_client()
    assert len(embeddings.embed_query("canone")) == config.EMBEDDING_DIM
    assert models.calls == [(["canone"], "RETRIEVAL_QUERY")]


def test_wrong_dimension_is_rejected(fake_client, monkeypatch) -> None:
    fake_client(dim=10)
    monkeypatch.setattr(embeddings.time, "sleep", lambda _s: None)
    with pytest.raises(ValueError):
        embeddings.embed_query("x")
