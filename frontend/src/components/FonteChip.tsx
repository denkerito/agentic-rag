import { useState } from 'react'
import { raggruppaFonti } from '../lib/fonti'
import { useFonte } from './FonteContext'

export function FonteChip({ id }: { id: string }) {
  const { apri } = useFonte()
  return (
    <button type="button" className="chip" onClick={() => apri(id)} title={`Apri la fonte ${id}`}>
      {id}
    </button>
  )
}

/** Elenco di chip; oltre `massimo` mostra un pulsante per espandere. */
export function IdChips({ ids, massimo = 8 }: { ids: string[]; massimo?: number }) {
  const [tutte, setTutte] = useState(false)
  if (ids.length === 0) return null
  const visibili = tutte ? ids : ids.slice(0, massimo)
  return (
    <span className="chips">
      {visibili.map((id) => (
        <FonteChip key={id} id={id} />
      ))}
      {ids.length > massimo && (
        <button type="button" className="link" onClick={() => setTutte(!tutte)}>
          {tutte ? 'mostra meno' : `+${ids.length - massimo} altre`}
        </button>
      )}
    </span>
  )
}

/** Fonti suddivise per categoria (Fatture, Movimenti, Documenti, ...). */
export function FontiRaggruppate({ ids }: { ids: string[] }) {
  return (
    <div>
      {raggruppaFonti(ids).map((g) => (
        <div key={g.categoria} className="gruppo-fonti">
          <span className="nome">
            {g.categoria} · {g.ids.length}
          </span>
          <IdChips ids={g.ids} massimo={6} />
        </div>
      ))}
    </div>
  )
}
