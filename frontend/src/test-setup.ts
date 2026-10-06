import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// senza `globals` Testing Library non registra da solo il cleanup tra un test e l'altro
afterEach(cleanup)
