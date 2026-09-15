import { defineConfig } from 'vitest/config'

/**
 * Config própria do Vitest: ele cuida da lógica pura, e o Playwright tem runner
 * e config próprios. Sem a exclusão, o Vitest tenta executar o spec de ponta a
 * ponta e falha — e a falha não diz isso com clareza.
 */
export default defineConfig({
  test: { exclude: ['e2e/**', 'node_modules/**', 'dist/**'] },
})
