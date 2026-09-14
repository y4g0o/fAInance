import { expect, it } from 'vitest'

import { dispensarLocalmente, type Insight } from './alertas'

const LISTA: Insight[] = [
  { id: 1, modulo: 'x', titulo: 'subiu', detalhe: {}, severidade: 'alerta', status: 'novo' },
  { id: 2, modulo: 'x', titulo: 'sumiu', detalhe: {}, severidade: 'info', status: 'novo' },
]

it('dispensar tira o alerta da lista na hora, sem esperar o servidor', () => {
  expect(dispensarLocalmente(LISTA, 1).map((i) => i.id)).toEqual([2])
})

it('dispensar id que não está na lista não apaga nada por engano', () => {
  expect(dispensarLocalmente(LISTA, 99)).toHaveLength(2)
})
