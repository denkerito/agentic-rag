// Speculare a src/agentic_rag/api/schemas.py e api/fonti.py: se cambiano là, cambiano qui.

export type Stato = 'in_coda' | 'in_corso' | 'completata' | 'fallita' | 'interrotta'

export const STATI_ATTIVI: readonly Stato[] = ['in_coda', 'in_corso']

export interface Numero {
  descrizione: string
  valore: string
  fonti: string[]
}

export interface Risposta {
  conclusione: string
  numeri: Numero[]
  fonti: string[]
  confidenza: 'alta' | 'media' | 'bassa'
  causa_documentata: boolean
  limiti: string | null
}

export interface IndagineRiga {
  id: string
  domanda: string
  stato: Stato
  creata_il: string
  conclusa_il: string | null
}

export interface IndagineDettaglio extends IndagineRiga {
  modello: string
  iniziata_il: string | null
  risposta: Risposta | null
  errore: string | null
  utilizzo: Record<string, number | null> | null
}

// Eventi SSE: `event:` = tipo, `id:` = seq, `data:` = il resto.
export interface ToolCall {
  tool_call_id: string
  tool: string
  args: Record<string, unknown>
}
export interface ToolResult {
  tool_call_id: string
  tool: string
  ids: string[]
  n_righe: number | null
  n_pertinenti: number | null
  troncato: boolean | null
  offset: number | null
}
export interface ToolRetry {
  tool_call_id: string
  tool: string
  motivo: string
}
export interface RispostaScartata {
  motivo: string
}
export interface RispostaFinale {
  risposta: Risposta
}
export interface Errore {
  errore: string
  messaggio: string
}
export interface Interrotta {
  motivo: string
}

interface PayloadPerTipo {
  tool_call: ToolCall
  tool_result: ToolResult
  tool_retry: ToolRetry
  risposta_scartata: RispostaScartata
  risposta: RispostaFinale
  errore: Errore
  interrotta: Interrotta
}

export type TipoEvento = keyof PayloadPerTipo
export const TIPI_EVENTO = [
  'tool_call',
  'tool_result',
  'tool_retry',
  'risposta_scartata',
  'risposta',
  'errore',
  'interrotta',
] as const satisfies readonly TipoEvento[]
export const TIPI_TERMINALI: readonly TipoEvento[] = ['risposta', 'errore', 'interrotta']

export type Evento = {
  [T in TipoEvento]: { tipo: T; seq: number } & PayloadPerTipo[T]
}[TipoEvento]

export type TipoFonte =
  | 'fattura'
  | 'riga_fattura'
  | 'movimento'
  | 'scrittura'
  | 'scadenza'
  | 'contratto'
  | 'documento'
  | 'cliente'
  | 'fornitore'

export interface Fonte {
  id: string
  tipo: TipoFonte
  titolo: string
  campi: { nome: string; valore: string | null }[]
  tabelle: { titolo: string; colonne: string[]; righe: (string | null)[][] }[]
  testo: string | null
  collegamenti: string[]
}

/** Stessi formati di ID_PATTERN (agent/ids.py): riconosce una fonte apribile. */
export const ID_FONTE =
  /^(?:FATT-[AP]-\d{4}-\d{4}|MOV-\d{6}|SCR-\d{6}|RIG-\d{4}|SCD-\d{4}|CTR-\d{3}|CLI-\d{3}|FOR-\d{3}|DOC-[A-Z]{3}-\d{3})$/
