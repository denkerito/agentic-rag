import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from google.genai import errors as genai_errors
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agentic_rag.agent.limiti import Limitatore, misura_attese
from agentic_rag.agent.tentativi import (
    POLITICA,
    ModelloGestito,
    PoliticaTentativi,
    da_ritentare,
    pausa,
)


def test_pausa_segue_la_cadenza_di_prima() -> None:
    assert [pausa(POLITICA, n, casuale=lambda: 0.0) for n in range(1, 6)] == [10, 20, 40, 60, 60]
    assert pausa(POLITICA, 1, casuale=lambda: 1.0) == 11


def test_da_ritentare() -> None:
    for codice in (429, 500, 502, 503, 504):
        assert da_ritentare(ModelHTTPError(status_code=codice, model_name="m"))
    assert da_ritentare(genai_errors.APIError(503, {}))
    assert da_ritentare(httpx.ConnectError("giù"))
    assert da_ritentare(httpx.ReadTimeout("lento"))
    assert da_ritentare(TimeoutError())  # timeout del singolo tentativo
    assert not da_ritentare(ModelHTTPError(status_code=400, model_name="m"))
    assert not da_ritentare(ModelHTTPError(status_code=404, model_name="m"))
    assert not da_ritentare(genai_errors.APIError(400, {}))
    assert not da_ritentare(UsageLimitExceeded("limite"))
    assert not da_ritentare(UnexpectedModelBehavior("output non valido"))
    assert not da_ritentare(asyncio.CancelledError())


# --- ModelloGestito ---------------------------------------------------------------------------


class Orologio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    async def dormi(self, s: float) -> None:
        self.t += s


def zero() -> float:
    return 0.0


class Provider:
    """FunctionModel che fallisce `n` volte con `codice` (ogni tentativo fallito dura 5 s)."""

    def __init__(self, o: Orologio, n: int, codice: int = 503) -> None:
        self.o, self.n, self.codice, self.chiamate = o, n, codice, 0

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.chiamate += 1
        if self.chiamate <= self.n:
            self.o.t += 5
            raise ModelHTTPError(status_code=self.codice, model_name="f")
        return ModelResponse(parts=[TextPart("ok")])


async def richiedi(modello: ModelloGestito) -> ModelResponse:
    return await modello.request(
        [ModelRequest.user_text_prompt("x")], None, ModelRequestParameters()
    )


def gestito(o: Orologio, p: Provider, **kw) -> ModelloGestito:
    kw.setdefault("limitatore", None)
    return ModelloGestito(FunctionModel(p), orologio=o, dormi=o.dormi, casuale=zero, **kw)


def test_503_poi_successo_ritenta_e_misura_tentativo_e_pausa() -> None:
    o = Orologio()
    p = Provider(o, 1)
    with misura_attese() as m:
        risposta = asyncio.run(richiedi(gestito(o, p)))
    assert risposta.parts[0].content == "ok"  # type: ignore[union-attr]
    assert m.secondi == 15.0 and m.tentativi_falliti == 1 and p.chiamate == 2


def test_esauriti_i_tentativi_rilancia_l_ultimo_errore() -> None:
    o = Orologio()
    p = Provider(o, 99)
    with misura_attese() as m, pytest.raises(ModelHTTPError) as e:
        asyncio.run(richiedi(gestito(o, p)))
    assert e.value.status_code == 503 and p.chiamate == 5
    assert m.secondi == 130 + 25 and m.tentativi_falliti == 5  # pause 10+20+40+60, 5 tentativi da 5 s


def test_errore_non_temporaneo_non_si_ritenta() -> None:
    o = Orologio()
    p = Provider(o, 1, codice=400)
    with misura_attese() as m, pytest.raises(ModelHTTPError):
        asyncio.run(richiedi(gestito(o, p)))
    assert p.chiamate == 1 and m.secondi == 0.0 and m.tentativi_falliti == 0


def test_ogni_tentativo_passa_dal_limitatore() -> None:
    # rpm=1: il primo tentativo fallisce (t=0→5), pausa fino a t=15, il secondo attende la finestra
    # fino a t=60 → misura = 5 (tentativo) + 10 (pausa) + 45 (limitatore)
    o = Orologio()
    p = Provider(o, 1)
    lim = Limitatore(rpm=1, tpm=None, orologio=o, dormi=o.dormi)
    with misura_attese() as m:
        asyncio.run(richiedi(gestito(o, p, limitatore=lim)))
    assert m.secondi == 60.0 and p.chiamate == 2


def test_timeout_del_tentativo_ritenta() -> None:
    chiamate = 0

    async def lenta_poi_ok(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal chiamate
        chiamate += 1
        if chiamate == 1:
            await asyncio.sleep(1)
        return ModelResponse(parts=[TextPart("ok")])

    politica = PoliticaTentativi(attesa_iniziale_s=0.0, jitter_s=0.0, timeout_tentativo_s=0.05)
    modello = ModelloGestito(FunctionModel(lenta_poi_ok), None, politica)
    with misura_attese() as m:
        risposta = asyncio.run(richiedi(modello))
    assert risposta.parts[0].content == "ok"  # type: ignore[union-attr]
    assert chiamate == 2 and m.tentativi_falliti == 1


async def leggi_stream(modello: ModelloGestito) -> str:
    async with modello.request_stream(
        [ModelRequest.user_text_prompt("x")], None, ModelRequestParameters()
    ) as s:
        async for _ in s:
            pass
    return "".join(p.content for p in s.get().parts if isinstance(p, TextPart))


def test_stream_ritenta_l_apertura() -> None:
    o = Orologio()
    chiamate = 0

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        nonlocal chiamate
        chiamate += 1
        if chiamate == 1:
            raise ModelHTTPError(status_code=503, model_name="f")
        yield "ok"

    modello = ModelloGestito(
        FunctionModel(stream_function=stream), None, orologio=o, dormi=o.dormi, casuale=zero
    )
    with misura_attese() as m:
        testo = asyncio.run(leggi_stream(modello))
    assert testo == "ok" and chiamate == 2 and m.tentativi_falliti == 1


def test_stream_errore_dopo_il_primo_evento_non_si_ritenta() -> None:
    o = Orologio()
    chiamate = 0

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        nonlocal chiamate
        chiamate += 1
        yield "a"
        raise ModelHTTPError(status_code=503, model_name="f")

    modello = ModelloGestito(
        FunctionModel(stream_function=stream), None, orologio=o, dormi=o.dormi, casuale=zero
    )
    with pytest.raises(ModelHTTPError):
        asyncio.run(leggi_stream(modello))
    assert chiamate == 1


def test_cancellazione_durante_la_pausa_si_propaga() -> None:
    p = Provider(Orologio(), 99)
    modello = ModelloGestito(FunctionModel(p), None, casuale=zero)  # dormi reale: pausa di 10 s

    async def scenario() -> None:
        task = asyncio.create_task(richiedi(modello))
        await asyncio.sleep(0.1)
        task.cancel()
        await task

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scenario())
    assert p.chiamate == 1


def test_senza_misura_attiva_funziona() -> None:
    o = Orologio()
    p = Provider(o, 1)
    risposta = asyncio.run(richiedi(gestito(o, p)))  # come nell'API: nessuna misura_attese()
    assert risposta.parts[0].content == "ok"  # type: ignore[union-attr]
