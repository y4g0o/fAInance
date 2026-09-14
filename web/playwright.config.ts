import { defineConfig } from '@playwright/test'

/**
 * O servidor é subido pelo próprio Playwright, num banco descartável semeado
 * pelo `e2e/servidor.sh`. Nenhum teste toca o banco real — teste que escreve no
 * banco de verdade é teste que um dia apaga o mês do usuário.
 */
const PORTA = 8020

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: { baseURL: `http://127.0.0.1:${PORTA}` },
  webServer: {
    command: './e2e/servidor.sh',
    url: `http://127.0.0.1:${PORTA}/api/saude`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
