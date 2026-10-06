export interface GruppoGiorno<T> {
  etichetta: 'Oggi' | 'Ieri' | 'Precedenti'
  items: T[]
}

const inizioGiorno = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

/** Raggruppa per giorno di calendario locale mantenendo l'ordine; i gruppi vuoti non compaiono. */
export function raggruppaPerGiorno<T>(
  items: T[],
  iso: (item: T) => string,
  adesso: Date = new Date(),
): GruppoGiorno<T>[] {
  const oggi = inizioGiorno(adesso)
  const ieri = oggi - 24 * 3600 * 1000
  const gruppi: GruppoGiorno<T>[] = [
    { etichetta: 'Oggi', items: [] },
    { etichetta: 'Ieri', items: [] },
    { etichetta: 'Precedenti', items: [] },
  ]
  for (const item of items) {
    const giorno = inizioGiorno(new Date(iso(item)))
    gruppi[giorno >= oggi ? 0 : giorno >= ieri ? 1 : 2].items.push(item)
  }
  return gruppi.filter((g) => g.items.length > 0)
}

/** Durata leggibile ("45 s", "2 min 05 s"); `fine` null = ancora in corso, si usa `adesso`. */
export function durata(inizio: string, fine: string | null, adesso: Date = new Date()): string {
  const ms = (fine ? new Date(fine) : adesso).getTime() - new Date(inizio).getTime()
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s} s`
  const min = Math.floor(s / 60)
  return `${min} min ${String(s % 60).padStart(2, '0')} s`
}
