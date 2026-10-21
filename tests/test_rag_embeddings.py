from types import SimpleNamespace

import pytest

from agentic_rag import config
from agentic_rag.agent.limiti import misura_attese
from agentic_rag.rag import embeddings


class FakeModels:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.calls: list[tuple[list[str], str]] = []

    def embed_content(self, *, model, contents, config):
        # embedding 2: un Content per testo (una lista di stringhe darebbe un solo vettore)
        testi = [c.parts[0].text for c in contents]
        self.calls.append((testi, config.task_type))
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


def test_embed_documents_batches_one_content_per_text(fake_client) -> None:
    models = fake_client()
    texts = [f"testo {i}" for i in range(embeddings.BATCH_SIZE + 5)]
    vectors = embeddings.embed_documents(texts)
    assert len(vectors) == len(texts)
    assert [len(c) for c, _ in models.calls] == [embeddings.BATCH_SIZE, 5]
    assert models.calls[0][0][0] == "testo 0"  # il formato dei documenti lo dà il chunking
    assert {t for _, t in models.calls} == {None}  # embedding 2 non accetta task_type


def test_embed_query_mette_il_compito_nel_testo(fake_client) -> None:
    models = fake_client()
    assert len(embeddings.embed_query("canone")) == config.EMBEDDING_DIM
    assert models.calls == [(["task: search result | query: canone"], None)]


def test_wrong_dimension_is_rejected(fake_client, monkeypatch) -> None:
    fake_client(dim=10)
    monkeypatch.setattr(embeddings.time, "sleep", lambda _s: None)
    with pytest.raises(ValueError):
        embeddings.embed_query("x")


def test_tentativi_e_pause_si_misurano_come_attesa(fake_client, monkeypatch) -> None:
    # dentro cerca_semantica le pause degli embedding non sono lavoro dell'agente
    models = fake_client()
    pause: list[float] = []
    monkeypatch.setattr(embeddings.time, "sleep", pause.append)
    originale = models.embed_content
    chiamate = {"n": 0}

    def instabile(**kw):
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            raise RuntimeError("503")
        return originale(**kw)

    monkeypatch.setattr(models, "embed_content", instabile)
    with misura_attese() as m:
        embeddings.embed_query("x")
    assert sum(pause) == 5 and pause == [1.0] * 5  # a passi: il watchdog vede l'attesa crescere
    assert m.tentativi_falliti == 1 and m.secondi >= 5


def test_il_rate_limiter_misura_l_attesa() -> None:
    t = [0.0]

    def dormi(s: float) -> None:
        t[0] += s

    lim = embeddings.RateLimiter(1, 10**9, clock=lambda: t[0], sleep=dormi)
    with misura_attese() as m:
        lim.acquire(1, 1)
        lim.acquire(1, 1)
    assert t[0] == 60 and m.secondi == 60
