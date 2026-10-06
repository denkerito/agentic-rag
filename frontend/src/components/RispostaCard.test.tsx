import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Risposta } from '../api/types'
import type { Passo } from '../state/passi'
import { FonteContext } from './FonteContext'
import { Passi } from './Passi'
import { RispostaCard } from './RispostaCard'

const risposta: Risposta = {
  conclusione: 'Il margine è sceso per i costi software.',
  numeri: [{ descrizione: 'Costi luglio', valore: '10.000,00 €', fonti: ['FATT-P-2025-0007'] }],
  fonti: ['FATT-P-2025-0007', 'CTR-001', 'DOC-NOT-002'],
  confidenza: 'media',
  causa_documentata: false,
  limiti: 'Nessun documento spiega il calo di novembre.',
}

describe('RispostaCard', () => {
  it('mostra confidenza, causa non documentata, limiti e numeri', () => {
    render(<RispostaCard risposta={risposta} />)
    expect(screen.getByText('Confidenza media')).toBeInTheDocument()
    expect(screen.getByText('Causa non documentata')).toBeInTheDocument()
    expect(screen.getByText(/Nessun documento spiega il calo di novembre/)).toBeInTheDocument()
    expect(screen.getByText('10.000,00 €')).toBeInTheDocument()
  })

  it('segnala la causa documentata', () => {
    render(<RispostaCard risposta={{ ...risposta, causa_documentata: true, limiti: null }} />)
    expect(screen.getByText('Causa documentata')).toBeInTheDocument()
    expect(screen.queryByText('Limiti')).not.toBeInTheDocument()
  })

  it('raggruppa le fonti citate per categoria con il conteggio', () => {
    render(<RispostaCard risposta={risposta} />)
    expect(screen.getByText('Fonti citate · 3')).toBeInTheDocument()
    expect(screen.getByText('Fatture · 1')).toBeInTheDocument()
    expect(screen.getByText('Contratti · 1')).toBeInTheDocument()
    expect(screen.getByText('Documenti · 1')).toBeInTheDocument()
  })

  it('il clic su una fonte chiede di aprirla', () => {
    const apri = vi.fn()
    render(
      <FonteContext value={{ apri }}>
        <RispostaCard risposta={risposta} />
      </FonteContext>,
    )
    const gruppo = screen.getByText('Contratti · 1').parentElement as HTMLElement
    fireEvent.click(within(gruppo).getByRole('button', { name: 'CTR-001' }))
    expect(apri).toHaveBeenCalledWith('CTR-001')
  })
})

describe('Passi', () => {
  const passi: Passo[] = [
    {
      kind: 'tool',
      callId: 'a',
      tool: 'query_sql',
      args: { sql: 'SELECT * FROM v_margine_mensile' },
      esito: {
        tool_call_id: 'a',
        tool: 'query_sql',
        ids: ['FATT-A-2025-0001'],
        n_righe: 12,
        n_pertinenti: null,
        troncato: false,
        offset: null,
      },
      retry: null,
    },
    {
      kind: 'tool',
      callId: 'b',
      tool: 'query_sql',
      args: { sql: 'SELECT x FROM nulla' },
      esito: null,
      retry: { tool_call_id: 'b', tool: 'query_sql', motivo: 'Errore SQL: tabella inesistente\n\nRiprova' },
    },
    { kind: 'tool', callId: 'c', tool: 'cerca_documenti', args: { query: 'chiusura' }, esito: null, retry: null },
    { kind: 'scartata', seq: 9, motivo: 'Fonti mai ricevute dai tool: PAGA-2025-08' },
  ]

  it('mostra la SQL (anteprima e testo completo), conteggio e fonti, ma non le righe', () => {
    render(<Passi passi={passi} />)
    expect(screen.getAllByText('SELECT * FROM v_margine_mensile')).toHaveLength(2) // summary + pre
    expect(screen.getByText('12 righe')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'FATT-A-2025-0001' })).toBeInTheDocument()
  })

  it('evidenzia retry e risposta scartata con il motivo', () => {
    render(<Passi passi={passi} />)
    expect(screen.getByText('Errore SQL: tabella inesistente')).toBeInTheDocument()
    expect(screen.getByText(/Risposta scartata dal controllo sulle fonti/)).toBeInTheDocument()
    expect(screen.getByText(/PAGA-2025-08/)).toBeInTheDocument()
  })

  it('un passo senza esito è "in esecuzione"', () => {
    render(<Passi passi={passi} />)
    expect(screen.getByRole('status', { name: 'In esecuzione' })).toBeInTheDocument()
  })

  it('si comprime e si riespande', () => {
    render(<Passi passi={passi} />)
    fireEvent.click(screen.getByRole('button', { name: 'Comprimi' }))
    expect(screen.queryByText('12 righe')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Espandi' }))
    expect(screen.getByText('12 righe')).toBeInTheDocument()
  })

  it('con l’indagine in corso mostra "sta ragionando" in coda alla timeline', () => {
    const { rerender } = render(<Passi passi={passi} inCorso />)
    expect(screen.getByText(/L'agente sta ragionando/)).toBeInTheDocument()
    rerender(<Passi passi={passi} />)
    expect(screen.queryByText(/L'agente sta ragionando/)).not.toBeInTheDocument()
  })
})
