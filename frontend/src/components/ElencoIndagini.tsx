import { NavLink } from 'react-router-dom'
import type { IndagineRiga } from '../api/types'
import { formatoData } from '../lib/formato'
import { StatoBadge } from './StatoBadge'

export function ElencoIndagini({
  indagini,
  errore,
}: {
  indagini: IndagineRiga[]
  errore: string | null
}) {
  return (
    <nav aria-label="Indagini precedenti" className="elenco">
      <h2>Indagini</h2>
      {errore && <p className="errore-testo">Elenco non disponibile: {errore}</p>}
      {!errore && indagini.length === 0 && <p className="muted">Nessuna indagine ancora.</p>}
      <ul>
        {indagini.map((i) => (
          <li key={i.id}>
            <NavLink to={`/indagini/${i.id}`}>
              <span className="domanda">{i.domanda}</span>
              <span className="meta">
                <StatoBadge stato={i.stato} />
                <span className="muted">{formatoData(i.creata_il)}</span>
              </span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
