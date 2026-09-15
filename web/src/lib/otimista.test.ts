import { describe, expect, it } from 'vitest'

import { aplicar, regraAmpla, reverter, type Grupo } from './otimista'

const GRUPOS: Grupo[] = [
  { padrao: 'deliveria', exemplo: 'PIX QRS DELIVERIA BR', ocorrencias: 10, total_centavos: 27995, alcance: 10 },
  { padrao: 'telecomix', exemplo: 'PIX QRS TELECOMIX', ocorrencias: 9, total_centavos: 61396, alcance: 9 },
]

describe('atualização otimista da tela de categorizar', () => {
  it('marca o grupo como aplicado antes de o servidor responder', () => {
    const depois = aplicar(GRUPOS, 'deliveria', 'Delivery')

    expect(depois.find((g) => g.padrao === 'deliveria')?.aplicado).toEqual({
      categoria: 'Delivery',
      confirmado: false,
    })
  })

  it('não mexe nos outros grupos', () => {
    const depois = aplicar(GRUPOS, 'deliveria', 'Delivery')

    expect(depois.find((g) => g.padrao === 'telecomix')?.aplicado).toBeUndefined()
  })

  it('reverte o grupo quando o servidor recusa', () => {
    const otimista = aplicar(GRUPOS, 'deliveria', 'Delivery')

    const revertido = reverter(otimista, 'deliveria', 'o servidor recusou')

    const grupo = revertido.find((g) => g.padrao === 'deliveria')
    expect(grupo?.aplicado).toBeUndefined()
    expect(grupo?.erro).toBe('o servidor recusou')
  })

  it('reverter devolve o grupo ao estado original, não a um estado inventado', () => {
    const revertido = reverter(aplicar(GRUPOS, 'deliveria', 'Delivery'), 'deliveria', 'falhou')

    const grupo = revertido.find((g) => g.padrao === 'deliveria')!
    expect(grupo.ocorrencias).toBe(10)
    expect(grupo.total_centavos).toBe(27995)
  })
})

describe('alcance da regra', () => {
  it('avisa quando a regra pega muito mais que o grupo', () => {
    // Caso real: grupo de 8 transações cujo padrão alcançava 45. Criar a regra
    // levaria junto 37 transações não relacionadas — foi assim que centenas de
    // compras viraram "movimentação" por engano.
    expect(regraAmpla({ ocorrencias: 8, alcance: 45 } as Grupo)).toBe(true)
  })

  it('não avisa quando o alcance é próximo do grupo', () => {
    expect(regraAmpla({ ocorrencias: 25, alcance: 26 } as Grupo)).toBe(false)
  })

  it('não avisa em grupo pequeno com alcance pequeno', () => {
    expect(regraAmpla({ ocorrencias: 2, alcance: 3 } as Grupo)).toBe(false)
  })
})
