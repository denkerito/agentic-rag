import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { ApiError, leggiFonte } from '../api/client'
import { ID_FONTE, type Fonte } from '../api/types'
import { ETICHETTA_TIPO } from '../lib/fonti'
import { FonteChip } from './FonteChip'
import { Icona } from './Icone'

interface Caricata {
  id: string
  fonte: Fonte | null
  errore: string | null
}

const umano = (nome: string) => nome.replaceAll('_', ' ')
const FOCALIZZABILI = 'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])'

export function FontePanel({ id, onChiudi }: { id: string | null; onChiudi: () => void }) {
  const [caricata, setCaricata] = useState<Caricata | null>(null)
  const pannello = useRef<HTMLElement>(null)
  const chiudiBtn = useRef<HTMLButtonElement>(null)
  const aperto = id !== null

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

  // focus nel pannello all'apertura, e di nuovo dove era prima alla chiusura
  useEffect(() => {
    if (!aperto) return
    const precedente = document.activeElement as HTMLElement | null
    chiudiBtn.current?.focus()
    return () => precedente?.focus?.()
  }, [aperto])

  useEffect(() => {
    if (!aperto) return
    const esc = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && onChiudi()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [aperto, onChiudi])

  // Tab resta dentro il pannello (aria-modal)
  function trappola(e: KeyboardEvent) {
    if (e.key !== 'Tab' || !pannello.current) return
    const el = [...pannello.current.querySelectorAll<HTMLElement>(FOCALIZZABILI)]
    if (el.length === 0) return
    const primo = el[0]
    const ultimo = el[el.length - 1]
    if (e.shiftKey && document.activeElement === primo) {
      e.preventDefault()
      ultimo.focus()
    } else if (!e.shiftKey && document.activeElement === ultimo) {
      e.preventDefault()
      primo.focus()
    }
  }

  if (!id) return null
  const pronta = caricata?.id === id ? caricata : null

  return (
    <>
      <div className="velo" onClick={onChiudi} aria-hidden="true" />
      <aside
        ref={pannello}
        className="pannello"
        role="dialog"
        aria-modal="true"
        aria-label={`Fonte ${id}`}
        onKeyDown={trappola}
      >
        <header className="pannello-testa">
          <div>
            <span className="pill accent">
              {pronta?.fonte ? ETICHETTA_TIPO[pronta.fonte.tipo] : 'Fonte'}
            </span>
            <h2>{id}</h2>
          </div>
          <button
            ref={chiudiBtn}
            type="button"
            className="btn-icona"
            onClick={onChiudi}
            aria-label="Chiudi"
          >
            <Icona nome="close" size={20} />
          </button>
        </header>
        <div className="pannello-corpo">
          {!pronta && <p className="muted">Caricamento…</p>}
          {pronta?.errore && <p className="errore-testo">{pronta.errore}</p>}
          {pronta?.fonte && <Dettaglio fonte={pronta.fonte} />}
        </div>
      </aside>
    </>
  )
}

function Dettaglio({ fonte }: { fonte: Fonte }) {
  return (
    <div>
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
        <div key={t.titolo}>
          <h4>{t.titolo}</h4>
          <div className="tabella-scroll">
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
                      <td key={j}>{v && ID_FONTE.test(v) ? <FonteChip id={v} /> : (v ?? '—')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
