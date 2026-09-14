/**
 * Atualização otimista dos grupos da tela de categorizar.
 *
 * Funções puras, sem React e sem rede: o estado da tela é decidido aqui e
 * testado sozinho. A falha clássica desse tipo de interface é mostrar sucesso
 * enquanto o banco não mudou — por isso `reverter` é parte da entrega, não
 * polimento, e devolve o grupo ao estado ORIGINAL em vez de a um estado
 * recalculado (que seria adivinhação).
 */
export type Grupo = {
  padrao: string
  exemplo: string
  ocorrencias: number
  total_centavos: number
  alcance: number
  aplicado?: { categoria: string; confirmado: boolean }
  erro?: string
}

/** Marca o grupo como aplicado ANTES de o servidor responder. */
export function aplicar(grupos: Grupo[], padrao: string, categoria: string): Grupo[] {
  return grupos.map((g) =>
    g.padrao === padrao
      ? { ...g, aplicado: { categoria, confirmado: false }, erro: undefined }
      : g,
  )
}

/** Confirma o que o servidor aceitou. */
export function confirmar(grupos: Grupo[], padrao: string): Grupo[] {
  return grupos.map((g) =>
    g.padrao === padrao && g.aplicado
      ? { ...g, aplicado: { ...g.aplicado, confirmado: true } }
      : g,
  )
}

/** Desfaz a marcação e diz por quê — o usuário precisa ver que não pegou. */
export function reverter(grupos: Grupo[], padrao: string, motivo: string): Grupo[] {
  return grupos.map((g) =>
    g.padrao === padrao ? { ...g, aplicado: undefined, erro: motivo } : g,
  )
}

/** Quanto do dinheiro sem categoria já foi resolvido — o progresso da tarefa. */
export function progresso(grupos: Grupo[]): { resolvido: number; total: number } {
  const total = grupos.reduce((soma, g) => soma + g.total_centavos, 0)
  const resolvido = grupos
    .filter((g) => g.aplicado)
    .reduce((soma, g) => soma + g.total_centavos, 0)
  return { resolvido, total }
}
