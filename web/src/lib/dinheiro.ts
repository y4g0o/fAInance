/**
 * Dinheiro é sempre inteiro de centavos, nunca float.
 *
 * O backend manda `valor_centavos` justamente para não existir ponto flutuante
 * no caminho: 0.1 + 0.2 não é 0.3 em JavaScript, e em dinheiro isso é erro de
 * verdade. Aqui só se formata para leitura — nenhuma conta acontece no front.
 */
export function formatar(centavos: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(centavos / 100)
}

/** Magnitude para exibição: o sinal vira contexto (entrada/saída), não texto. */
export function formatarMagnitude(centavos: number): string {
  return formatar(Math.abs(centavos))
}
