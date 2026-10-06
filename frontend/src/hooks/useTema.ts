import { useCallback, useState } from 'react'

export type Tema = 'sistema' | 'chiaro' | 'scuro'

export const CHIAVE_TEMA = 'tema'
const TEMI: readonly Tema[] = ['sistema', 'chiaro', 'scuro']

export function leggiTema(): Tema {
  try {
    const salvato = localStorage.getItem(CHIAVE_TEMA)
    return TEMI.includes(salvato as Tema) ? (salvato as Tema) : 'sistema'
  } catch {
    return 'sistema' // storage bloccato (navigazione privata, politiche del browser)
  }
}

/** `sistema` toglie l'attributo: i token seguono prefers-color-scheme. */
export function applicaTema(tema: Tema): void {
  const radice = document.documentElement
  if (tema === 'sistema') radice.removeAttribute('data-theme')
  else radice.setAttribute('data-theme', tema === 'chiaro' ? 'light' : 'dark')
}

export function useTema(): [Tema, (tema: Tema) => void] {
  const [tema, setTemaState] = useState<Tema>(leggiTema)
  const setTema = useCallback((nuovo: Tema) => {
    setTemaState(nuovo)
    applicaTema(nuovo)
    try {
      localStorage.setItem(CHIAVE_TEMA, nuovo)
    } catch {
      // la scelta vale per la sessione, ma non viene ricordata
    }
  }, [])
  return [tema, setTema]
}
