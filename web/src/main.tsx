import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { REGISTRO } from './composicao'
import { Shell } from './shell/Shell'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Shell registro={REGISTRO} />
  </StrictMode>,
)
