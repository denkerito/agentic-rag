import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { Composer } from './Composer'

vi.mock('../api/client')

const ricaricaElenco = vi.fn()

function montato() {
  return render(
    <MemoryRouter>
      <Routes>
        <Route element={<Outlet context={{ ricaricaElenco }} />}>
          <Route index element={<Composer />} />
          <Route path="indagini/:id" element={<p>vista indagine</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe('Composer', () => {
  it('l’invio è disabilitato finché la domanda è vuota', () => {
    montato()
    expect(screen.getByRole('button', { name: 'Avvia indagine' })).toBeDisabled()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } })
    expect(screen.getByRole('button', { name: 'Avvia indagine' })).toBeDisabled()
  })

  it('avvia l’indagine e passa alla sua pagina', async () => {
    vi.mocked(client.creaIndagine).mockResolvedValue({ id: 'abc', stato: 'in_coda' })
    montato()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  Qual è il margine?  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Avvia indagine' }))
    await waitFor(() => expect(screen.getByText('vista indagine')).toBeInTheDocument())
    expect(client.creaIndagine).toHaveBeenCalledWith('Qual è il margine?')
    expect(ricaricaElenco).toHaveBeenCalled()
  })

  it('mostra l’errore se l’avvio fallisce', async () => {
    vi.mocked(client.creaIndagine).mockRejectedValue(new Error('rete'))
    montato()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'domanda' } })
    fireEvent.click(screen.getByRole('button', { name: 'Avvia indagine' }))
    expect(await screen.findByText(/Impossibile avviare/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Avvia indagine' })).toBeEnabled()
  })
})
