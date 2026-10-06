import { Link } from 'react-router-dom'

// barre del logo: [x, altezza]; con `lavora` pulsano a turno
const BARRE: [number, number][] = [
  [5.8, 5],
  [10.8, 10],
  [15.8, 6],
  [20.8, 12],
]

export function Marchio({ lavora = false }: { lavora?: boolean }) {
  return (
    <Link
      to="/"
      className={`marchio ${lavora ? 'lavora' : ''}`}
      aria-label="Indagini economiche, home"
    >
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
        <rect width="28" height="28" rx="8" fill="var(--accent)" />
        {BARRE.map(([x, h]) => (
          <rect key={x} className="b" x={x} y={19 - h} width="2.4" height={h} rx="1.2" fill="var(--accent-fg)" />
        ))}
      </svg>
      Indagini economiche
    </Link>
  )
}
