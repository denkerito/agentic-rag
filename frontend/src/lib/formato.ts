export const formatoData = (iso: string) =>
  new Date(iso).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })
