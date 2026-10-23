import type { ToolResult } from '../api/types'
import type { NomeIcona } from '../components/Icone'

/** Titolo e icona dei tool dell'agente nei passi dell'indagine. */
export const TOOL: Record<string, { titolo: string; icona: NomeIcona }> = {
  query_sql: { titolo: 'Query SQL', icona: 'database' },
  elenca_documenti: { titolo: 'Elenco documenti', icona: 'file' },
  cerca_testo: { titolo: 'Ricerca testuale', icona: 'search' },
  cerca_semantica: { titolo: 'Ricerca semantica', icona: 'search' },
  // nome della ricerca semantica nelle indagini salvate prima della rinomina
  cerca_documenti: { titolo: 'Ricerca nei documenti', icona: 'search' },
  apri_documento: { titolo: 'Apertura documento', icona: 'file' },
}

const plurale = (n: number, uno: string, molti: string) => `${n} ${n === 1 ? uno : molti}`

/** Riepilogo di una riga dell'esito di un tool. */
export function riepilogo(tool: string, esito: ToolResult): string {
  if (tool === 'query_sql') {
    // anteprima: il risultato era troppo grande, l'agente deve aggregare o filtrare
    if (esito.troncato && esito.totale) {
      return `Anteprima: ${plurale(esito.n_righe ?? 0, 'riga', 'righe')} su ${esito.totale} (va aggregato)`
    }
    return `${plurale(esito.n_righe ?? 0, 'riga', 'righe')}${esito.troncato ? ' (risultato troncato)' : ''}`
  }
  if (tool === 'elenca_documenti') {
    const totale = esito.totale ?? 0
    if (!totale) return 'Nessun documento'
    return `${plurale(totale, 'documento', 'documenti')} · pagina ${esito.pagina ?? 1} di ${esito.pagine ?? 1}`
  }
  if (tool === 'cerca_testo') {
    const n = esito.n_pertinenti ?? 0
    if (!n) return 'Nessuna corrispondenza'
    return `${plurale(n, 'documento', 'documenti')} con corrispondenza su ${esito.totale ?? n}`
  }
  if (tool === 'cerca_semantica' || tool === 'cerca_documenti') {
    return esito.n_pertinenti
      ? plurale(esito.n_pertinenti, 'risultato pertinente', 'risultati pertinenti')
      : 'Nessun documento pertinente'
  }
  return esito.troncato ? 'Documento aperto (parte troncata)' : 'Documento aperto'
}
