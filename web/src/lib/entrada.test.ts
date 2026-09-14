import { expect, it } from 'vitest'

import { motivoDoValorInvalido, valorAceitavel } from './entrada'

it('aceita o jeito que o brasileiro digita', () => {
  for (const bom of ['7,50', '1.234,56', '50', '89,9', '3000']) {
    expect(valorAceitavel(bom), bom).toBe(true)
  }
})

it('recusa valor que começa com separador', () => {
  // O modelo local já produziu ".8990" para "89,90" — leitura como 0,90 seria
  // erro de 100x. Aqui a mesma classe de entrada é barrada na tela.
  expect(motivoDoValorInvalido('.8990')).toMatch(/não pode começar/)
})

it('explica que o sinal vem do tipo, não do número', () => {
  expect(motivoDoValorInvalido('-50')).toMatch(/sempre positivo/)
})

it('não reclama de valor válido', () => {
  expect(motivoDoValorInvalido('1.234,56')).toBeNull()
})
