import type { Fonte, IndagineDettaglio, IndagineRiga } from './types'

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function richiesta<T>(percorso: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${percorso}`, init)
  if (!res.ok) {
    let dettaglio = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') dettaglio = body.detail
    } catch {
      // corpo non JSON: resta lo statusText
    }
    throw new ApiError(res.status, dettaglio)
  }
  return (await res.json()) as T
}

export const creaIndagine = (domanda: string) =>
  richiesta<{ id: string; stato: string }>('/indagini', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ domanda }),
  })

export const elencoIndagini = () => richiesta<IndagineRiga[]>('/indagini?limit=50')

export const dettaglioIndagine = (id: string) => richiesta<IndagineDettaglio>(`/indagini/${id}`)

export const fermaIndagine = (id: string) =>
  richiesta<unknown>(`/indagini/${id}/stop`, { method: 'POST' })

export const leggiFonte = (id: string) => richiesta<Fonte>(`/fonti/${encodeURIComponent(id)}`)

export const urlEventi = (id: string) => `${API_BASE}/indagini/${id}/eventi`
