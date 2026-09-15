import { execFileSync } from 'node:child_process'

import { expect, test } from '@playwright/test'

const BANCO = process.env.PERSONALOS_E2E_DB ?? '/tmp/personalos-e2e.db'

/** Lê o banco direto, sem passar pela API: prova que o efeito é real e não só visual. */
function categoriasNoBanco(): Record<string, number> {
  const saida = execFileSync('../.venv/bin/python', [
    '-c',
    `import sqlite3, json, sys
c = sqlite3.connect(sys.argv[1])
linhas = c.execute("select coalesce(categoria,'-'), count(*) from financas_transacoes group by 1").fetchall()
print(json.dumps(dict(linhas)))`,
    BANCO,
  ])
  return JSON.parse(saida.toString())
}

test('categorizar um grupo pela tela muda o banco, e desfazer volta', async ({ page }) => {
  await page.goto('/app/')

  await page.getByRole('button', { name: 'Categorizar' }).click()

  // O grupo maior aparece primeiro: a ordenação é por dinheiro, não por contagem.
  const linha = page.locator('tr', { hasText: 'deliveria' })
  await expect(linha).toBeVisible()

  await linha.locator('input[list="categorias-existentes"]').fill('Delivery')
  await linha.getByRole('button', { name: 'Aplicar' }).click()

  // Efeito na tela…
  await expect(linha.getByText('Delivery')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Desfazer' })).toBeVisible()

  // …e efeito no banco, que é o que importa.
  await expect(() => {
    expect(categoriasNoBanco()['Delivery']).toBe(10)
  }).toPass({ timeout: 5_000 })

  await page.getByRole('button', { name: 'Desfazer' }).click()

  await expect(() => {
    expect(categoriasNoBanco()['Delivery']).toBeUndefined()
  }).toPass({ timeout: 5_000 })
})

test('a operação não recarrega a página', async ({ page }) => {
  await page.goto('/app/')
  await page.getByRole('button', { name: 'Categorizar' }).click()

  // Marca o documento: se houver reload, a marca se perde.
  await page.evaluate(() => {
    ;(window as unknown as { __marca?: number }).__marca = 42
  })

  const linha = page.locator('tr', { hasText: 'telecomix' })
  await linha.locator('input[list="categorias-existentes"]').fill('Serviços')
  await linha.getByRole('button', { name: 'Aplicar' }).click()
  await expect(linha.getByText('Serviços')).toBeVisible()

  const marca = await page.evaluate(
    () => (window as unknown as { __marca?: number }).__marca,
  )
  expect(marca, 'a página recarregou — a marca no window se perdeu').toBe(42)
})
