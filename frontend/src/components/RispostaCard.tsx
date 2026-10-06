import type { Risposta } from '../api/types'
import { IdChips } from './FonteChip'

export function RispostaCard({ risposta }: { risposta: Risposta }) {
  return (
    <section className="card risposta" aria-label="Risposta">
      <header>
        <h2>Risposta</h2>
        <span className={`badge conf-${risposta.confidenza}`}>
          Confidenza {risposta.confidenza}
        </span>
        <span className={`badge ${risposta.causa_documentata ? 'ok' : 'neutro'}`}>
          {risposta.causa_documentata ? 'Causa documentata' : 'Causa non documentata'}
        </span>
      </header>
      <p className="conclusione">{risposta.conclusione}</p>

      {risposta.numeri.length > 0 && (
        <table className="numeri">
          <thead>
            <tr>
              <th>Dato</th>
              <th>Valore</th>
              <th>Fonti</th>
            </tr>
          </thead>
          <tbody>
            {risposta.numeri.map((n) => (
              <tr key={`${n.descrizione}|${n.valore}`}>
                <td>{n.descrizione}</td>
                <td className="valore">{n.valore}</td>
                <td>
                  <IdChips ids={n.fonti} massimo={4} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {risposta.limiti && (
        <div className="limiti">
          <strong>Limiti</strong>
          <p>{risposta.limiti}</p>
        </div>
      )}

      <div className="fonti-risposta">
        <strong>Fonti citate</strong> <IdChips ids={risposta.fonti} massimo={12} />
      </div>
    </section>
  )
}
