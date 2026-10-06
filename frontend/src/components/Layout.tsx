import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Outlet, useLocation, useSearchParams } from 'react-router-dom'
import { STATI_ATTIVI } from '../api/types'
import { useElenco } from '../hooks/useElenco'
import type { LayoutContext } from '../lib/layoutContext'
import { ElencoIndagini } from './ElencoIndagini'
import { FonteContext } from './FonteContext'
import { FontePanel } from './FontePanel'
import { Icona } from './Icone'
import { Marchio } from './Marchio'
import { ThemeToggle } from './ThemeToggle'

export default function Layout() {
  const [params, setParams] = useSearchParams()
  const { pathname } = useLocation()
  const { indagini, errore, ricarica } = useElenco()
  const lavora = indagini.some((i) => STATI_ATTIVI.includes(i.stato))

  // su mobile il cassetto si chiude da solo quando si naviga (ricorda in quale pagina è stato aperto)
  const [apertoSu, setApertoSu] = useState<string | null>(null)
  const menuAperto = apertoSu === pathname
  const setMenuAperto = useCallback((v: boolean) => setApertoSu(v ? pathname : null), [pathname])

  useEffect(() => {
    if (!menuAperto) return
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setMenuAperto(false)
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [menuAperto, setMenuAperto])

  // la fonte aperta sta nell'URL (?fonte=ID): link condivisibile, sopravvive al reload
  const apri = useCallback(
    (id: string) =>
      setParams((p) => {
        const n = new URLSearchParams(p)
        n.set('fonte', id)
        return n
      }),
    [setParams],
  )
  const chiudi = useCallback(
    () =>
      setParams((p) => {
        const n = new URLSearchParams(p)
        n.delete('fonte')
        return n
      }),
    [setParams],
  )
  const fonteCtx = useMemo(() => ({ apri }), [apri])
  const outletCtx: LayoutContext = useMemo(() => ({ ricaricaElenco: ricarica }), [ricarica])

  return (
    <FonteContext value={fonteCtx}>
      <div className="shell">
        <header className="topbar">
          <button
            type="button"
            className="btn-icona"
            aria-label="Apri il menu"
            aria-expanded={menuAperto}
            onClick={() => setMenuAperto(true)}
          >
            <Icona nome="menu" size={20} />
          </button>
          <Marchio lavora={lavora} />
        </header>
        <div
          className={`velo-menu ${menuAperto ? 'aperto' : ''}`}
          onClick={() => setMenuAperto(false)}
          aria-hidden="true"
        />
        <aside className={`barra ${menuAperto ? 'aperta' : ''}`} aria-label="Navigazione">
          <Marchio lavora={lavora} />
          <Link to="/" className="btn primario pieno">
            <Icona nome="plus" size={16} /> Nuova indagine
          </Link>
          <div className="barra-elenco">
            <ElencoIndagini indagini={indagini} errore={errore} />
          </div>
          <div className="barra-pie">
            <ThemeToggle />
          </div>
        </aside>
        <main className="contenuto">
          <Outlet context={outletCtx} />
        </main>
        <FontePanel id={params.get('fonte')} onChiudi={chiudi} />
      </div>
    </FonteContext>
  )
}
