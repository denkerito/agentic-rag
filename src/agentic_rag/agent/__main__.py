"""Uso: python -m agentic_rag.agent "domanda"."""

import sys

from agentic_rag.agent.run import investigate


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Uso: python -m agentic_rag.agent "domanda"')
    risposta, deps = investigate(" ".join(sys.argv[1:]))
    print("== Passi ==")
    for i, ev in enumerate(deps.trace, 1):
        detail = {k: v for k, v in ev.items() if k != "kind"}
        print(f"{i:>2}. {ev['kind']}: {detail}")
    print("\n== Risposta ==")
    print(risposta.conclusione)
    for n in risposta.numeri:
        print(f"  - {n.descrizione}: {n.valore} [{', '.join(n.fonti)}]")
    print(f"\nFonti: {', '.join(risposta.fonti)}")
    print(f"Confidenza: {risposta.confidenza} | causa documentata: {risposta.causa_documentata}")
    if risposta.limiti:
        print(f"Limiti: {risposta.limiti}")


if __name__ == "__main__":
    main()
