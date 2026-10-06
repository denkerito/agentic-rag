import type { TipoFonte } from '../api/types'

export const ETICHETTA_TIPO: Record<TipoFonte, string> = {
  fattura: 'Fattura',
  riga_fattura: 'Riga di fattura',
  movimento: 'Movimento bancario',
  scrittura: 'Scrittura contabile',
  scadenza: 'Scadenza',
  contratto: 'Contratto',
  documento: 'Documento',
  cliente: 'Cliente',
  fornitore: 'Fornitore',
}

// ordine di presentazione: prima i dati contabili, poi i documenti
const CATEGORIE: { prefisso: string; nome: string }[] = [
  { prefisso: 'FATT', nome: 'Fatture' },
  { prefisso: 'RIG', nome: 'Righe di fattura' },
  { prefisso: 'MOV', nome: 'Movimenti bancari' },
  { prefisso: 'SCR', nome: 'Scritture contabili' },
  { prefisso: 'SCD', nome: 'Scadenze' },
  { prefisso: 'CTR', nome: 'Contratti' },
  { prefisso: 'DOC', nome: 'Documenti' },
  { prefisso: 'CLI', nome: 'Clienti' },
  { prefisso: 'FOR', nome: 'Fornitori' },
]
const ALTRE = 'Altre fonti'

export interface GruppoFonti {
  categoria: string
  ids: string[]
}

/** Raggruppa gli ID per categoria (nell'ordine sopra); dentro il gruppo gli ID sono ordinati e unici. */
export function raggruppaFonti(ids: string[]): GruppoFonti[] {
  const gruppi = new Map<string, Set<string>>()
  for (const id of ids) {
    const prefisso = id.split('-', 1)[0]
    const nome = CATEGORIE.find((c) => c.prefisso === prefisso)?.nome ?? ALTRE
    gruppi.set(nome, (gruppi.get(nome) ?? new Set()).add(id))
  }
  const ordine = [...CATEGORIE.map((c) => c.nome), ALTRE]
  return ordine
    .filter((nome) => gruppi.has(nome))
    .map((nome) => ({ categoria: nome, ids: [...gruppi.get(nome)!].sort() }))
}
