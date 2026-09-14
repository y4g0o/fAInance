import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// O build vai direto para dentro do pacote Python: quem serve a SPA em uso normal
// é o próprio FastAPI, num processo só. O dev server abaixo existe apenas enquanto
// se programa, e manda /api para o backend real.
//
// base '/app/' porque o painel Jinja ainda ocupa a raiz durante o P1 (spec: ele só
// se aposenta no fim do P2).
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  build: {
    outDir: '../src/personalos/web_dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
