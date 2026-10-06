export const formatoData = (iso: string) =>
  new Date(iso).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })

export const formatoOra = (iso: string) =>
  new Date(iso).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })

export const formatoGiornoOra = (iso: string) =>
  new Date(iso).toLocaleString('it-IT', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
