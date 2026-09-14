import { expect, it } from 'vitest'

import { formatar, formatarMagnitude } from './dinheiro'

it('formata centavos inteiros no padrão brasileiro', () => {
  expect(formatar(123456).replace(/ /g, ' ')).toBe('R$ 1.234,56')
})

it('não perde centavo em valor que floats erram', () => {
  // 0.1 + 0.2 !== 0.3 em JavaScript. Trabalhar em inteiro é o que evita isso.
  expect(formatar(10 + 20).replace(/ /g, ' ')).toBe('R$ 0,30')
})

it('magnitude tira o sinal, porque o sinal vira contexto na tela', () => {
  expect(formatarMagnitude(-8990)).toBe(formatarMagnitude(8990))
})
