/**
 * Validação de entrada de dinheiro, antes de incomodar o servidor.
 *
 * O parse de verdade é do domínio em Python (`Dinheiro.de_texto`) — aqui só se
 * evita ida e volta óbvia. O valor viaja como TEXTO e quem interpreta é o
 * backend: duas regras de parse seria duas verdades sobre o mesmo número.
 */
const VALOR = /^\d{1,3}(\.\d{3})*(,\d{1,2})?$|^\d+([.,]\d{1,2})?$/

export function valorAceitavel(texto: string): boolean {
  return VALOR.test(texto.trim())
}

export function motivoDoValorInvalido(texto: string): string | null {
  const limpo = texto.trim()
  if (!limpo) return 'informe o valor'
  if (limpo.startsWith('-'))
    return 'o valor é sempre positivo — quem decide entrada ou saída é o tipo'
  if (/^[.,]/.test(limpo)) return 'valor não pode começar com vírgula ou ponto'
  if (!valorAceitavel(limpo)) return 'use só dígitos, com até 2 casas decimais (ex: 89,90)'
  return null
}
