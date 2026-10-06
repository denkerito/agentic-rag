import { useState } from 'react'
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
          {tutte ? 'meno' : `+${ids.length - massimo} altre`}
        </button>
      )}
    </span>
  )
}
