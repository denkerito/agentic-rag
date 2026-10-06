import { describe, expect, it } from 'vitest'
import { durata, raggruppaPerGiorno } from './data'

const adesso = new Date(2025, 9, 6, 15, 0, 0) // 6 ottobre 2025, ore 15 (ora locale)
const alle = (g: number, h: number) => new Date(2025, 9, g, h, 0, 0).toISOString()

describe('raggruppaPerGiorno', () => {
  it('separa Oggi, Ieri e Precedenti mantenendo l’ordine', () => {
    const items = [
      { id: 'a', t: alle(6, 14) },
      { id: 'b', t: alle(6, 9) },
      { id: 'c', t: alle(5, 23) },
      { id: 'd', t: alle(1, 10) },
    ]
    const g = raggruppaPerGiorno(items, (i) => i.t, adesso)
    expect(g.map((x) => [x.etichetta, x.items.map((i) => i.id)])).toEqual([
      ['Oggi', ['a', 'b']],
      ['Ieri', ['c']],
      ['Precedenti', ['d']],
    ])
  })

  it('omette i gruppi vuoti', () => {
    const g = raggruppaPerGiorno([{ t: alle(2, 10) }], (i) => i.t, adesso)
    expect(g.map((x) => x.etichetta)).toEqual(['Precedenti'])
  })
})

describe('durata', () => {
  const inizio = new Date(2025, 9, 6, 15, 0, 0).toISOString()
  const dopo = (s: number) => new Date(2025, 9, 6, 15, 0, s).toISOString()

  it('secondi e minuti', () => {
    expect(durata(inizio, dopo(45))).toBe('45 s')
    expect(durata(inizio, dopo(125))).toBe('2 min 05 s')
  })

  it('se in corso usa l’ora attuale', () => {
    expect(durata(inizio, null, new Date(2025, 9, 6, 15, 0, 30))).toBe('30 s')
  })

  it('non va sotto zero', () => {
    expect(durata(dopo(10), inizio)).toBe('0 s')
  })
})
