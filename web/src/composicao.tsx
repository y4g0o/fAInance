/**
 * Composição: a única camada que sabe QUAL módulo tem QUAL tela.
 *
 * Espelha `composicao.py` do backend, e pelo mesmo motivo: a moldura não pode
 * conhecer módulo nenhum, então o mapeamento precisa morar fora dela. Módulo
 * novo entra aqui, e em mais lugar nenhum.
 */
import { TelaFinancas } from './modulos/financas/TelaFinancas'
import type { Registro } from './shell/Shell'

export const REGISTRO: Registro = {
  financas: { titulo: 'Finanças', Tela: TelaFinancas },
}
