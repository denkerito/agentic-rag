import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TestoRivelato } from './TestoRivelato'

describe('TestoRivelato', () => {
  it('lascia il testo completo e invariato per gli screen reader', () => {
    const testo = 'Il margine è sceso del 12,5% (FATT-A-2025-0050).'
    render(<TestoRivelato testo={testo} />)
    expect(screen.getByText(testo)).toHaveClass('sr-only')
  })

  it('anima una parola per volta, con ritardo crescente e limitato', () => {
    const { container } = render(<TestoRivelato testo={Array(40).fill('a').join(' ')} />)
    const parole = [...container.querySelectorAll<HTMLElement>('.parola')]
    expect(parole).toHaveLength(40)
    expect(parole[0].style.getPropertyValue('--w')).toBe('0')
    expect(parole[5].style.getPropertyValue('--w')).toBe('5')
    expect(parole[39].style.getPropertyValue('--w')).toBe('28')
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument()
  })
})
