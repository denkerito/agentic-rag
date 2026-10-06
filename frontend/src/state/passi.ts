import type {
  Errore,
  Evento,
  Risposta,
  ToolResult,
  ToolRetry,
} from '../api/types'

export interface PassoTool {
  kind: 'tool'
  callId: string
  tool: string
  args: Record<string, unknown>
  esito: ToolResult | null
  retry: ToolRetry | null
}

export interface PassoScartato {
  kind: 'scartata'
  seq: number
  motivo: string
}

export type Passo = PassoTool | PassoScartato

export interface Vista {
  passi: Passo[]
  risposta: Risposta | null
  errore: Errore | null
  interrotta: string | null
  ultimoSeq: number
}

export const vistaIniziale: Vista = {
  passi: [],
  risposta: null,
  errore: null,
  interrotta: null,
  ultimoSeq: 0,
}

export function terminata(v: Vista): boolean {
  return v.risposta !== null || v.errore !== null || v.interrotta !== null
}

function aggiornaTool(
  passi: Passo[],
  callId: string,
  patch: Partial<Pick<PassoTool, 'esito' | 'retry'>>,
): Passo[] {
  return passi.map((p) => (p.kind === 'tool' && p.callId === callId ? { ...p, ...patch } : p))
}

/** Applica un evento alla vista. Gli eventi già visti (seq <= ultimoSeq) sono ignorati:
 *  alla riconnessione dello stream il server può rimandarli. */
export function riduci(v: Vista, e: Evento): Vista {
  if (e.seq <= v.ultimoSeq) return v
  const base = { ...v, ultimoSeq: e.seq }
  switch (e.tipo) {
    case 'tool_call':
      return {
        ...base,
        passi: [
          ...v.passi,
          {
            kind: 'tool',
            callId: e.tool_call_id,
            tool: e.tool,
            args: e.args,
            esito: null,
            retry: null,
          },
        ],
      }
    case 'tool_result':
      return { ...base, passi: aggiornaTool(v.passi, e.tool_call_id, { esito: e }) }
    case 'tool_retry':
      return { ...base, passi: aggiornaTool(v.passi, e.tool_call_id, { retry: e }) }
    case 'risposta_scartata':
      return { ...base, passi: [...v.passi, { kind: 'scartata', seq: e.seq, motivo: e.motivo }] }
    case 'risposta':
      return { ...base, risposta: e.risposta }
    case 'errore':
      return { ...base, errore: { errore: e.errore, messaggio: e.messaggio } }
    case 'interrotta':
      return { ...base, interrotta: e.motivo }
  }
}
