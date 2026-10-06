import { describe, expect, it } from 'vitest'
import { raggruppaFonti } from './fonti'

describe('raggruppaFonti', () => {
  it('raggruppa per categoria, nell’ordine contabile poi documenti', () => {
    const g = raggruppaFonti([
      'DOC-NOT-002',
      'MOV-000170',
      'FATT-P-2025-0008',
      'FATT-A-2025-0050',
      'CTR-001',
    ])
    expect(g.map((x) => x.categoria)).toEqual([
      'Fatture',
      'Movimenti bancari',
      'Contratti',
      'Documenti',
    ])
    expect(g[0].ids).toEqual(['FATT-A-2025-0050', 'FATT-P-2025-0008'])
  })

  it('elimina i duplicati e mette gli ID sconosciuti in coda', () => {
    const g = raggruppaFonti(['CLI-001', 'CLI-001', 'PAGA-2025-08'])
    expect(g).toEqual([
      { categoria: 'Clienti', ids: ['CLI-001'] },
      { categoria: 'Altre fonti', ids: ['PAGA-2025-08'] },
    ])
  })

  it('lista vuota: nessun gruppo', () => {
    expect(raggruppaFonti([])).toEqual([])
  })
})
