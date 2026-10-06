import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { applicaTema, CHIAVE_TEMA, leggiTema, useTema } from './useTema'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})
afterEach(() => vi.restoreAllMocks())

describe('useTema', () => {
  it('parte da "sistema" senza attributo', () => {
    const { result } = renderHook(() => useTema())
    expect(result.current[0]).toBe('sistema')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('chiaro e scuro impostano data-theme e vengono ricordati', () => {
    const { result } = renderHook(() => useTema())
    act(() => result.current[1]('scuro'))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem(CHIAVE_TEMA)).toBe('scuro')
    act(() => result.current[1]('chiaro'))
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(leggiTema()).toBe('chiaro')
  })

  it('tornando a "sistema" toglie l’attributo', () => {
    applicaTema('scuro')
    applicaTema('sistema')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('un valore salvato non valido vale "sistema"', () => {
    localStorage.setItem(CHIAVE_TEMA, 'blu')
    expect(leggiTema()).toBe('sistema')
  })

  it('funziona anche se localStorage non è disponibile', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloccato')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloccato')
    })
    const { result } = renderHook(() => useTema())
    expect(result.current[0]).toBe('sistema')
    act(() => result.current[1]('scuro'))
    expect(result.current[0]).toBe('scuro')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})
