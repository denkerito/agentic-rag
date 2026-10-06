import { useEffect, useState } from 'react'
import { ApiError, leggiFonte } from '../api/client'
import { ID_FONTE, type Fonte } from '../api/types'
import { FonteChip } from './FonteChip'

interface Caricata {
  id: string
  fonte: Fonte | null
  errore: string | null
}

const umano = (nome: string) => nome.replaceAll('_', ' ')

export function FontePanel({ id, onChiudi }: { id: string | null; onChiudi: () => void }) {
  const [caricata, setCaricata] = useState<Caricata | null>(null)

  useEffect(() => {
    if (!id) return
    let attuale = true
    leggiFonte(id)
      .then((fonte) => attuale && setCaricata({ id, fonte, errore: null }))
      .catch((e) => {
        const msg = e instanceof ApiError && e.status === 404 ? 'Fonte non trovata.' : String(e)
        if (attuale) setCaricata({ id, fonte: null, errore: msg })
      })
    return () => {
      attuale = false
    }
  }, [id])

  useEffect(() => {
    if (!id) return
    const chiudiConEsc = (e: KeyboardEvent) => e.key === 'Escape' && onChiudi()
    window.addEventListener('keydown', chiudiConEsc)
    return () => window.removeEventListener('keydown', chiudiConEsc)
  }, [id, onChiudi])

  if (!id) return null
  const pronta = caricata?.id === id ? caricata : null

  return (
    <aside className="drawer" role="dialog" aria-label={`Fonte ${id}`}>
      <header>
        <div>
          <p className="muted">{pronta?.fonte ? umano(pronta.fonte.tipo) : 'Fonte'}</p>
          <h2>{id}</h2>
        </div>
        <button type="button" className="link" onClick={onChiudi} aria-label="Chiudi">
          ✕
        </button>
      </header>
      {!pronta && <p className="muted">Caricamento…</p>}
      {pronta?.errore && <p className="errore-testo">{pronta.errore}</p>}
      {pronta?.fonte && <Dettaglio fonte={pronta.fonte} />}
    </aside>
  )
}

function Dettaglio({ fonte }: { fonte: Fonte }) {
  return (
    <div className="drawer-body">
      <h3>{fonte.titolo}</h3>
      <dl className="campi">
        {fonte.campi.map((c) => (
          <div key={c.nome}>
            <dt>{umano(c.nome)}</dt>
            <dd>{c.valore ?? '—'}</dd>
          </div>
        ))}
      </dl>
      {fonte.tabelle.map((t) => (
        <div key={t.titolo} className="tabella-scroll">
          <h4>{t.titolo}</h4>
          <table>
            <thead>
              <tr>
                {t.colonne.map((c) => (
                  <th key={c}>{umano(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {t.righe.map((r, i) => (
                <tr key={i}>
                  {r.map((v, j) => (
                    <td key={j}>
                      {v && ID_FONTE.test(v) ? <FonteChip id={v} /> : (v ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {fonte.collegamenti.length > 0 && (
        <div>
          <h4>Collegamenti</h4>
          <span className="chips">
            {fonte.collegamenti.map((c) => (
              <FonteChip key={c} id={c} />
            ))}
          </span>
        </div>
      )}
      {fonte.testo && (
        <div>
          <h4>Testo</h4>
          <pre className="testo">{fonte.testo}</pre>
        </div>
      )}
    </div>
  )
}
