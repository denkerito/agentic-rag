import { useCallback, useMemo } from 'react'
import { Link, Outlet, useSearchParams } from 'react-router-dom'
import { useElenco } from '../hooks/useElenco'
import { ElencoIndagini } from './ElencoIndagini'
import { FonteContext } from './FonteContext'
import { FontePanel } from './FontePanel'
import { NuovaIndagine } from './NuovaIndagine'
import type { LayoutContext } from './VistaIndagine'

export default function Layout() {
  const [params, setParams] = useSearchParams()
  const { indagini, errore, ricarica } = useElenco()

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
      <div className="app">
        <aside className="barra">
          <Link to="/" className="titolo">
            Indagini economiche
          </Link>
          <NuovaIndagine onCreata={ricarica} />
          <ElencoIndagini indagini={indagini} errore={errore} />
        </aside>
        <main>
          <Outlet context={outletCtx} />
        </main>
        <FontePanel id={params.get('fonte')} onChiudi={chiudi} />
      </div>
    </FonteContext>
  )
}
