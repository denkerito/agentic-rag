import asyncio

from agentic_rag.agent.limiti import Limitatore, dormi_misurato, limitatore_per, misura_attese


class Orologio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    async def dormi(self, s: float) -> None:
        self.t += s


def test_rpm_fa_attendere_la_richiesta_oltre_il_limite() -> None:
    o = Orologio()
    lim = Limitatore(rpm=2, tpm=None, orologio=o, dormi=o.dormi)

    async def tre() -> list[float]:
        return [await lim.attendi() for _ in range(3)]

    with misura_attese() as m:
        attese = asyncio.run(tre())
    assert attese[:2] == [0.0, 0.0]
    assert attese[2] == 60.0  # la prima richiesta esce dalla finestra dopo 60 s
    assert m.secondi == 60.0  # l'attesa è visibile a chi misura (eval: latenza e timeout)


def test_tpm_conta_i_token_usati_nella_finestra() -> None:
    o = Orologio()
    lim = Limitatore(rpm=None, tpm=1000, orologio=o, dormi=o.dormi)

    async def scenario() -> tuple[float, float]:
        prima = await lim.attendi()
        lim.registra_token(1200)
        o.t += 10
        seconda = await lim.attendi()
        return prima, seconda

    prima, seconda = asyncio.run(scenario())
    assert prima == 0.0 and seconda == 50.0  # i token di t=0 escono dalla finestra a t=60


def test_senza_limiti_nessun_limitatore_e_istanza_condivisa_per_modello() -> None:
    assert limitatore_per("agente", "m-senza", None, None) is None
    a = limitatore_per("agente", "m-condiviso", 10, None)
    assert a is limitatore_per("agente", "m-condiviso", 10, None)
    assert a is not limitatore_per("giudice", "m-condiviso", 10, None)


def test_dormi_misurato_somma_a_passi() -> None:
    o = Orologio()
    visti: list[float] = []

    async def dormi(s: float) -> None:
        visti.append(m.secondi)  # misura vista dal watchdog durante la pausa
        await o.dormi(s)

    with misura_attese() as m:
        asyncio.run(dormi_misurato(2.5, dormi))
    assert m.secondi == 2.5
    assert visti == [0.0, 1.0, 2.0]  # cresce passo per passo, non tutta alla fine
