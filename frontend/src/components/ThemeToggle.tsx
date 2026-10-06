import { useTema, type Tema } from '../hooks/useTema'
import { Icona, type NomeIcona } from './Icone'

const OPZIONI: { valore: Tema; etichetta: string; icona: NomeIcona }[] = [
  { valore: 'sistema', etichetta: 'Sistema', icona: 'monitor' },
  { valore: 'chiaro', etichetta: 'Chiaro', icona: 'sun' },
  { valore: 'scuro', etichetta: 'Scuro', icona: 'moon' },
]

export function ThemeToggle() {
  const [tema, setTema] = useTema()
  return (
    <div className="tema" role="radiogroup" aria-label="Tema">
      {OPZIONI.map((o) => (
        <button
          key={o.valore}
          type="button"
          role="radio"
          aria-checked={tema === o.valore}
          onClick={() => setTema(o.valore)}
        >
          <Icona nome={o.icona} size={14} />
          {o.etichetta}
        </button>
      ))}
    </div>
  )
}
