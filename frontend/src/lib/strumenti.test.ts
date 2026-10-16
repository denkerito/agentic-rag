import { describe, expect, it } from 'vitest'
import type { ToolResult } from '../api/types'
import { riepilogo, TOOL } from './strumenti'

const esito = (campi: Partial<ToolResult>): ToolResult => ({
  tool_call_id: 'c',
  tool: 't',
  ids: [],
  n_righe: null,
  n_pertinenti: null,
  troncato: null,
  offset: null,
  ...campi,
})

describe('riepilogo', () => {
  it('elenco documenti: totale e pagina', () => {
    expect(riepilogo('elenca_documenti', esito({ totale: 12, pagina: 1, pagine: 1 }))).toBe(
      '12 documenti · pagina 1 di 1',
    )
    expect(riepilogo('elenca_documenti', esito({ totale: 0 }))).toBe('Nessun documento')
  })

  it('ricerca testuale: restituiti su totale, o nessuna corrispondenza', () => {
    expect(riepilogo('cerca_testo', esito({ n_pertinenti: 3, totale: 7 }))).toBe(
      '3 documenti con corrispondenza su 7',
    )
    expect(riepilogo('cerca_testo', esito({ n_pertinenti: 0, totale: 0 }))).toBe(
      'Nessuna corrispondenza',
    )
  })

  it('ricerca semantica, anche col nome delle indagini salvate prima della rinomina', () => {
    for (const tool of ['cerca_semantica', 'cerca_documenti']) {
      expect(riepilogo(tool, esito({ n_pertinenti: 1 }))).toBe('1 risultato pertinente')
      expect(riepilogo(tool, esito({ n_pertinenti: 0 }))).toBe('Nessun documento pertinente')
    }
  })

  it('ogni tool ha un titolo, compreso il nome storico', () => {
    for (const tool of ['elenca_documenti', 'cerca_testo', 'cerca_semantica', 'cerca_documenti']) {
      expect(TOOL[tool]?.titolo).toBeTruthy()
    }
  })
})
