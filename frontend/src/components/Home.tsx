import type { CSSProperties } from 'react'
import { Composer } from './Composer'
import { seguiPuntatore } from '../lib/spotlight'
import { Icona, type NomeIcona } from './Icone'

const PRINCIPI: { icona: NomeIcona; titolo: string; testo: string }[] = [
  {
    icona: 'calc',
    titolo: 'I numeri vengono dal database',
    testo: 'Somme, confronti e percentuali sono calcolati da query SQL in sola lettura, mai a mente dal modello.',
  },
  {
    icona: 'link',
    titolo: 'Ogni dato ha una fonte',
    testo: 'Fatture, movimenti, contratti e documenti citati si aprono con un clic, per controllarli.',
  },
  {
    icona: 'shield',
    titolo: 'Se non lo sa, lo dice',
    testo: "Quando una causa non è documentata, l'agente lo dichiara invece di inventarla.",
  },
]

export default function Home() {
  return (
    <div className="pagina home" onPointerMove={seguiPuntatore}>
      <div className="aurora" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <h1>
        Indaga i <span className="gradiente">dati economici</span> dell'azienda
      </h1>
      <p className="lead">
        Fai una domanda: l'agente interroga database e documenti, mostra ogni passo e ti consegna una
        risposta con numeri e fonti verificabili.
      </p>
      <Composer />
      <div className="principi">
        {PRINCIPI.map((p, i) => (
          <section
            key={p.titolo}
            className="principio"
            style={{ '--i': i } as CSSProperties}
            onPointerMove={seguiPuntatore}
          >
            <h3>
              <span className="tile">
                <Icona nome={p.icona} size={17} />
              </span>
              {p.titolo}
            </h3>
            <p>{p.testo}</p>
          </section>
        ))}
      </div>
    </div>
  )
}
