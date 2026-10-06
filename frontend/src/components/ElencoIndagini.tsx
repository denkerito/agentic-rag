import { NavLink } from 'react-router-dom'
import type { IndagineRiga } from '../api/types'
import { raggruppaPerGiorno } from '../lib/data'
import { formatoGiornoOra, formatoOra } from '../lib/formato'
import { StatoDot } from './StatoBadge'

export function ElencoIndagini({
  indagini,
  errore,
}: {
  indagini: IndagineRiga[]
  errore: string | null
}) {
  const gruppi = raggruppaPerGiorno(indagini, (i) => i.creata_il)
  return (
    <nav aria-label="Indagini precedenti" className="elenco">
      {errore && <p className="errore-testo">Elenco non disponibile: {errore}</p>}
      {!errore && indagini.length === 0 && (
        <p className="muted" style={{ padding: '0 8px', fontSize: 'var(--t-s)' }}>
          Nessuna indagine ancora.
        </p>
      )}
      {gruppi.map((g) => (
        <section key={g.etichetta}>
          <h2>{g.etichetta}</h2>
          <ul>
            {g.items.map((i) => (
              <li key={i.id}>
                <NavLink to={`/indagini/${i.id}`}>
                  <StatoDot stato={i.stato} />
                  <span className="domanda">{i.domanda}</span>
                  <span className="ora">
                    {g.etichetta === 'Precedenti'
                      ? formatoGiornoOra(i.creata_il)
                      : formatoOra(i.creata_il)}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </nav>
  )
}
