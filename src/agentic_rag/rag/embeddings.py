"""Embedding Gemini con throttling (RPM/TPM) e retry."""

import time
from collections import deque
from collections.abc import Callable
from functools import cache

from google import genai
from google.genai import types

from agentic_rag import config

BATCH_SIZE = 20
MAX_RETRIES = 5
CHARS_PER_TOKEN = 3  # stima per eccesso (misurato ~3,8 sui documenti reali)


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN + 1


class RateLimiter:
    """Finestra mobile di 60 s su richieste (un testo = una richiesta) e token stimati."""

    def __init__(
        self,
        max_rpm: int,
        max_tpm: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_rpm, self.max_tpm = max_rpm, max_tpm
        self._clock, self._sleep = clock, sleep
        self._events: deque[tuple[float, int, int]] = deque()  # (t, richieste, token)

    def _prune(self, now: float) -> None:
        while self._events and now - self._events[0][0] >= 60:
            self._events.popleft()

    def acquire(self, requests: int, tokens: int) -> None:
        if requests > self.max_rpm or tokens > self.max_tpm:
            raise ValueError("batch più grande del limite per minuto")
        while True:
            now = self._clock()
            self._prune(now)
            used_r = sum(e[1] for e in self._events)
            used_t = sum(e[2] for e in self._events)
            if used_r + requests <= self.max_rpm and used_t + tokens <= self.max_tpm:
                self._events.append((now, requests, tokens))
                return
            self._sleep(max(0.5, 60 - (now - self._events[0][0])))


@cache
def get_client() -> genai.Client:
    if not config.GOOGLE_API_KEY:
        raise SystemExit("GOOGLE_API_KEY non impostata (vedi .env.example)")
    return genai.Client(api_key=config.GOOGLE_API_KEY)


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    response = get_client().models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type, output_dimensionality=config.EMBEDDING_DIM
        ),
    )
    return [list(e.values or []) for e in response.embeddings or []]


_limiter = RateLimiter(config.EMBEDDING_MAX_RPM, config.EMBEDDING_MAX_TPM)


def _with_retry[T](call: Callable[[], T]) -> T:
    for attempt in range(MAX_RETRIES):
        try:
            return call()
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(min(60, 5 * 2**attempt))  # un 429 sui limiti per minuto richiede attesa
    raise AssertionError("unreachable")


def _check(vectors: list[list[float]], expected: int) -> list[list[float]]:
    if len(vectors) != expected or any(len(v) != config.EMBEDDING_DIM for v in vectors):
        raise ValueError("risposta embedding con numero o dimensione inattesi")
    return vectors


def embed_documents(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        _limiter.acquire(len(batch), sum(estimate_tokens(t) for t in batch))
        vectors += _check(
            _with_retry(lambda b=batch: _embed(b, "RETRIEVAL_DOCUMENT")),
            len(batch),
        )
    return vectors


def embed_query(text: str) -> list[float]:
    _limiter.acquire(1, estimate_tokens(text))
    return _check(_with_retry(lambda: _embed([text], "RETRIEVAL_QUERY")), 1)[0]
