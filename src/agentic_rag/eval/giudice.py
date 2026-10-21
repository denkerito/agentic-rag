"""Giudice LLM opzionale (--judge): la conclusione dell'agente coincide con la risposta attesa?"""

from pydantic_ai import Agent

from agentic_rag.agent import config as agent_config
from agentic_rag.agent.model import build_model
from agentic_rag.agent.output import Risposta
from agentic_rag.eval.valutazione import Giudizio

ISTRUZIONI = """\
Sei un valutatore rigoroso. Confronti la risposta di un agente con la risposta attesa.
- corretta: individua la stessa causa o lo stesso esito e i dati essenziali della risposta attesa.
- parziale: coglie solo una parte della causa o dei dati, oppure è corretta ma incompleta.
- errata: indica una causa diversa, contraddice la risposta attesa, o inventa ciò che la risposta
  attesa dichiara non documentato.
Giudica il contenuto, non lo stile. Se la risposta attesa dice che una causa non è documentata,
la risposta è corretta solo se l'agente lo dichiara. Motiva in due frasi al massimo.
"""


def giudica(
    domanda: str, risposta_attesa: str, risposta: Risposta, model: str | None = None
) -> Giudizio:
    # niente temperature: i modelli con ragionamento accettano solo quella di default
    agent = Agent(
        build_model(model or agent_config.JUDGE_MODEL, ruolo="giudice"),
        output_type=Giudizio,
        instructions=ISTRUZIONI,
        retries=2,
    )
    prompt = (
        f"Domanda: {domanda}\n\n"
        f"Risposta attesa:\n{risposta_attesa}\n\n"
        f"Risposta dell'agente:\n{risposta.conclusione}\n"
        f"Causa documentata dichiarata: {risposta.causa_documentata}\n"
        f"Limiti dichiarati: {risposta.limiti or 'nessuno'}"
    )
    return agent.run_sync(prompt).output
