import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePlaceholder } from './usePlaceholder'

const FRASI = ['Ciao mondo', 'Altra frase'] as const
const BASE = 'Scrivi…'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('usePlaceholder', () => {
  it('parte dal testo base, poi "scrive" la prima frase', () => {
    const { result } = renderHook(() => usePlaceholder(FRASI, true, BASE))
    expect(result.current).toBe(BASE)
    act(() => void vi.advanceTimersByTime(700 + 38 * 3))
    expect(result.current.startsWith('Ciao')).toBe(true)
    act(() => void vi.advanceTimersByTime(38 * 20))
    expect(result.current.startsWith('Ciao mondo')).toBe(true)
  })

  it('dopo la pausa cancella e passa alla frase successiva', () => {
    const { result } = renderHook(() => usePlaceholder(FRASI, true, BASE))
    act(() => void vi.advanceTimersByTime(700 + 38 * 12 + 1800 + 16 * 12 + 350 + 38 * 4))
    expect(result.current.startsWith('Altr')).toBe(true)
  })

  it('se non attivo (l’utente ha scritto) restituisce il testo base', () => {
    const { result } = renderHook(() => usePlaceholder(FRASI, false, BASE))
    act(() => void vi.advanceTimersByTime(5000))
    expect(result.current).toBe(BASE)
  })

  it('con movimento ridotto non anima', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    const { result } = renderHook(() => usePlaceholder(FRASI, true, BASE))
    act(() => void vi.advanceTimersByTime(5000))
    expect(result.current).toBe(BASE)
  })
})
