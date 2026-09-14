/**
 * Alertas do kernel. Mora no shell porque insight é conceito do PersonalOS
 * inteiro, não de um módulo: cada módulo PRODUZ insights, e esta lista apenas
 * os apresenta, com o nome do módulo vindo como dado, nunca hardcoded.
 */
export type Insight = {
  id: number
  modulo: string
  titulo: string
  detalhe: Record<string, unknown>
  severidade: string
  status: string
}

/** Tira o alerta da lista na hora — o servidor confirma depois. */
export function dispensarLocalmente(insights: Insight[], id: number): Insight[] {
  return insights.filter((i) => i.id !== id)
}
