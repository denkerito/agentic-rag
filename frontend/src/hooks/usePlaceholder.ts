import { useEffect, useState } from 'react'

const riduciMovimento = () =>
  typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** Placeholder che "scrive" a rotazione le `frasi` finché `attivo`; altrimenti (o con movimento
 *  ridotto) restituisce `base`. `frasi` deve essere stabile (costante di modulo). */
export function usePlaceholder(frasi: readonly string[], attivo: boolean, base: string): string {
  const [animato, setAnimato] = useState('')

  useEffect(() => {
    if (!attivo || riduciMovimento()) return
    let i = 0
    let k = 0
    let fase: 'scrive' | 'cancella' = 'scrive'
    let t: ReturnType<typeof setTimeout>

    const passo = () => {
      const frase = frasi[i]
      if (fase === 'scrive') {
        k += 1
        setAnimato(frase.slice(0, k))
        if (k === frase.length) {
          fase = 'cancella'
          t = setTimeout(passo, 1800) // pausa a frase completa
        } else t = setTimeout(passo, 38)
      } else {
        k -= 1
        setAnimato(frase.slice(0, k))
        if (k === 0) {
          fase = 'scrive'
          i = (i + 1) % frasi.length
          t = setTimeout(passo, 350)
        } else t = setTimeout(passo, 16)
      }
    }
    t = setTimeout(passo, 700)
    return () => clearTimeout(t)
  }, [attivo, frasi])

  return attivo && animato && !riduciMovimento() ? `${animato} ▏` : base
}
