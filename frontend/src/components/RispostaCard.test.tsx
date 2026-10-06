import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Risposta } from '../api/types'
import type { Passo } from '../state/passi'
import { FonteContext } from './FonteContext'
import { Passi } from './Passi'
import { RispostaCard } from './RispostaCard'

const risposta: Risposta = {
  conclusione: 'Il margine è sceso per i costi software.',
  numeri: [{ descrizione: 'Costi luglio', valore: '10.000,00 €', fonti: ['FATT-P-2025-0007'] }],
  fonti: ['FATT-P-2025-0007', 'CTR-001'],
  confidenza: 'media',
  causa_documentata: false,
  limiti: 'Nessun documento spiega il calo di novembre.',
}

describe('RispostaCard', () => {
  it('mostra confidenza, causa non documentata, limiti e fonti', () => {
    render(<RispostaCard risposta={risposta} />)
    expect(screen.getByText('Confidenza media')).toBeInTheDocument()
    expect(screen.getByText('Causa non documentata')).toBeInTheDocument()
    expect(screen.getByText('Nessun documento spiega il calo di novembre.')).toBeInTheDocument()
    expect(screen.getByText('10.000,00 €')).toBeInTheDocument()
  })

  it('il clic su una fonte chiede di aprirla', () => {
    const apri = vi.fn()
    render(
      <FonteContext value={{ apri }}>
        <RispostaCard risposta={risposta} />
      </FonteContext>,
    )
    fireEvent.click(screen.getAllByRole('button', { name: 'CTR-001' })[0])
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
    { kind: 'scartata', seq: 3, motivo: 'Fonti mai ricevute dai tool: PAGA-2025-08' },
  ]

  it('mostra SQL, conteggi, fonti e la risposta scartata, ma non le righe', () => {
    render(<Passi passi={passi} />)
    expect(screen.getByText('SELECT * FROM v_margine_mensile')).toBeInTheDocument()
    expect(screen.getByText('12 righe')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'FATT-A-2025-0001' })).toBeInTheDocument()
    expect(screen.getByText(/scartata dal controllo sulle fonti/)).toBeInTheDocument()
    expect(screen.getByText(/PAGA-2025-08/)).toBeInTheDocument()
  })
})
