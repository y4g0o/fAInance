/**
 * Geometria dos gráficos — função pura, testada sozinha.
 *
 * A barra do dobro do valor precisa ter o dobro do comprimento: gráfico que
 * mente na proporção é pior que tabela, porque convence.
 */

/** Escala 0..100 sobre o maior valor da série. Série vazia devolve zero, não NaN. */
export function escala(valores: number[]): (v: number) => number {
  const maior = Math.max(0, ...valores.map(Math.abs))
  return (v: number) => (maior === 0 ? 0 : (Math.abs(v) / maior) * 100)
}

export type Fatia = { rotulo: string; centavos: number; percentual: number }

/** Ordena por magnitude e calcula a participação de cada uma. */
export function fatias(itens: { rotulo: string; centavos: number }[]): Fatia[] {
  const total = itens.reduce((soma, i) => soma + Math.abs(i.centavos), 0)
  if (total === 0) return []
  return itens
    .map((i) => ({ ...i, percentual: (Math.abs(i.centavos) / total) * 100 }))
    .sort((a, b) => Math.abs(b.centavos) - Math.abs(a.centavos))
}


export type MesFluxo = { mes: string; entradas: number; saidas: number }

/**
 * Escala única para entradas E saídas.
 *
 * Escalas separadas são a mentira clássica do gráfico de dois eixos: uma saída
 * menor pode parecer maior que uma entrada maior. Aqui as duas dividem o mesmo
 * teto, então a altura é comparável entre elas.
 */
export function escalaFluxo(meses: MesFluxo[]): (v: number) => number {
  return escala(meses.flatMap((m) => [m.entradas, m.saidas]))
}

/** Sobra do mês, com sinal: positivo sobrou, negativo faltou. */
export function resultado(m: MesFluxo): number {
  return m.entradas - m.saidas
}
