import { describe, expect, it } from 'vitest'
import type { Evento, Risposta } from '../api/types'
import { riduci, terminata, vistaIniziale, type Vista } from './passi'

const call = (seq: number, id: string, tool = 'query_sql'): Evento => ({
  tipo: 'tool_call',
  seq,
  tool_call_id: id,
  tool,
  args: { sql: 'SELECT 1' },
})
const result = (seq: number, id: string): Evento => ({
  tipo: 'tool_result',
  seq,
  tool_call_id: id,
  tool: 'query_sql',
  ids: ['FATT-A-2025-0001'],
  n_righe: 3,
  n_pertinenti: null,
  troncato: false,
  offset: null,
})
const risposta: Risposta = {
  conclusione: 'ok',
  numeri: [],
  fonti: ['FATT-A-2025-0001'],
  confidenza: 'alta',
  causa_documentata: false,
  limiti: null,
}
const applica = (eventi: Evento[]): Vista => eventi.reduce(riduci, vistaIniziale)

describe('riduci', () => {
  it('unisce chiamata ed esito dello stesso tool_call_id in un solo passo', () => {
    const v = applica([call(1, 'a'), result(2, 'a')])
    expect(v.passi).toHaveLength(1)
    expect(v.passi[0]).toMatchObject({ kind: 'tool', callId: 'a', esito: { n_righe: 3 } })
    expect(v.ultimoSeq).toBe(2)
  })

  it('un passo senza esito resta in attesa', () => {
    const v = applica([call(1, 'a')])
    expect(v.passi[0]).toMatchObject({ esito: null, retry: null })
  })

  it('associa il retry alla chiamata rifiutata e non ad altre', () => {
    const v = applica([
      call(1, 'a'),
      { tipo: 'tool_retry', seq: 2, tool_call_id: 'a', tool: 'query_sql', motivo: 'errore' },
      call(3, 'b'),
    ])
    expect(v.passi[0]).toMatchObject({ retry: { motivo: 'errore' } })
    expect(v.passi[1]).toMatchObject({ retry: null, esito: null })
  })

  it('mostra la risposta scartata come passo a sé, nell’ordine di arrivo', () => {
    const v = applica([
      call(1, 'a'),
      result(2, 'a'),
      { tipo: 'risposta_scartata', seq: 3, motivo: 'fonti mai viste' },
      call(4, 'b'),
    ])
    expect(v.passi.map((p) => p.kind)).toEqual(['tool', 'scartata', 'tool'])
    expect(v.risposta).toBeNull()
  })

  it('ignora gli eventi già visti (riconnessione dello stream)', () => {
    const v = applica([call(1, 'a'), result(2, 'a'), call(1, 'a'), result(2, 'a')])
    expect(v.passi).toHaveLength(1)
  })

  it.each([
    ['risposta', { tipo: 'risposta', seq: 5, risposta } as Evento],
    ['errore', { tipo: 'errore', seq: 5, errore: 'modello', messaggio: 'HTTP 503' } as Evento],
    ['interrotta', { tipo: 'interrotta', seq: 5, motivo: 'Fermata dall’utente' } as Evento],
  ])('l’evento terminale «%s» chiude la vista', (_nome, evento) => {
    const v = applica([call(1, 'a'), evento])
    expect(terminata(v)).toBe(true)
    expect(terminata(applica([call(1, 'a')]))).toBe(false)
  })

  it('espone risposta, errore e motivo di interruzione', () => {
    expect(applica([{ tipo: 'risposta', seq: 1, risposta }]).risposta?.conclusione).toBe('ok')
    expect(
      applica([{ tipo: 'errore', seq: 1, errore: 'x', messaggio: 'm' }]).errore?.messaggio,
    ).toBe('m')
    expect(applica([{ tipo: 'interrotta', seq: 1, motivo: 'stop' }]).interrotta).toBe('stop')
  })
})
