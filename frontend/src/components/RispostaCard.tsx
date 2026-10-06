import type { CSSProperties } from 'react'
import type { Risposta } from '../api/types'
import { FontiRaggruppate, IdChips } from './FonteChip'
import { Icona } from './Icone'
import { TestoRivelato } from './TestoRivelato'

export function RispostaCard({ risposta }: { risposta: Risposta }) {
  return (
    <section className="card risposta" aria-label="Risposta">
      <header className="risposta-testa">
        <h2>Risposta</h2>
        <span className="confidenza" data-livello={risposta.confidenza}>
          <span className="segmenti" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>Confidenza {risposta.confidenza}</span>
        </span>
        <span className={`pill ${risposta.causa_documentata ? 'ok' : ''}`}>
          {risposta.causa_documentata ? 'Causa documentata' : 'Causa non documentata'}
        </span>
      </header>

      <TestoRivelato testo={risposta.conclusione} className="conclusione" />

      {risposta.numeri.length > 0 && (
        <table className="numeri">
          <thead>
            <tr>
              <th>Dato</th>
              <th className="valore">Valore</th>
              <th>Fonti</th>
            </tr>
          </thead>
          <tbody>
            {risposta.numeri.map((n, i) => (
              <tr key={`${n.descrizione}|${n.valore}`} style={{ '--i': i } as CSSProperties}>
                <td>{n.descrizione}</td>
                <td className="valore">{n.valore}</td>
                <td>
                  <IdChips ids={n.fonti} massimo={3} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {risposta.limiti && (
        <div className="callout" role="note">
          <Icona nome="alert" size={18} />
          <div>
            <strong>Limiti</strong>
            {risposta.limiti}
          </div>
        </div>
      )}

      <div className="fonti-gruppi">
        <h3>Fonti citate · {risposta.fonti.length}</h3>
        <FontiRaggruppate ids={risposta.fonti} />
      </div>
    </section>
  )
}
