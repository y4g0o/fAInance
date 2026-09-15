import { describe, expect, it } from 'vitest'

import { escala, escalaFluxo, fatias, resultado } from './grafico'

it('a barra do dobro do valor tem o dobro do comprimento', () => {
  const e = escala([100, 200, 50])

  expect(e(200)).toBe(100)
  expect(e(100)).toBe(50)
})

it('escala de série vazia não explode nem divide por zero', () => {
  expect(escala([])(10)).toBe(0)
  expect(escala([0, 0])(0)).toBe(0)
})

it('as fatias somam 100% e a maior vem primeiro', () => {
  const f = fatias([
    { rotulo: 'a', centavos: 2500 },
    { rotulo: 'b', centavos: 7500 },
  ])

  expect(f[0].rotulo).toBe('b')
  expect(f.reduce((s, x) => s + x.percentual, 0)).toBeCloseTo(100)
})

it('fatia sem dado nenhum devolve lista vazia, não uma fatia de 0%', () => {
  // Zero fingindo dado é o que a regra "sem dado é sem dado" proíbe.
  expect(fatias([])).toEqual([])
})

describe('fluxo com entradas e saídas', () => {
  const MESES = [
    { mes: '2026-06', entradas: 500000, saidas: 300000 },
    { mes: '2026-07', entradas: 250000, saidas: 400000 },
  ]

  it('usa a MESMA escala para entrada e saída', () => {
    // Escalas separadas fariam uma saída menor parecer maior que uma entrada
    // maior — a mentira clássica de gráfico com dois eixos.
    const e = escalaFluxo(MESES)

    expect(e(500000)).toBe(100)
    expect(e(250000)).toBe(50)
    expect(e(400000)).toBe(80)
  })

  it('o resultado do mês é entrada menos saída, com sinal', () => {
    expect(resultado(MESES[0])).toBe(200000)
    expect(resultado(MESES[1])).toBe(-150000)
  })

  it('série vazia não quebra a escala', () => {
    expect(escalaFluxo([])(100)).toBe(0)
  })
})
