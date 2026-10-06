import { createContext, useContext } from 'react'

interface FonteContextValue {
  /** Apre il pannello della fonte (ID FATT-*, CTR-*, DOC-*, ...). */
  apri: (id: string) => void
}

export const FonteContext = createContext<FonteContextValue>({ apri: () => {} })

export const useFonte = () => useContext(FonteContext)
