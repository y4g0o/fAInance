import { expect, it } from 'vitest'

import { LIMITE_BYTES, problemaNoArquivo } from './arquivos'

function falso(nome: string, bytes = 1000) {
  return new File([new Uint8Array(bytes)], nome)
}

it('aceita os formatos que o sistema sabe ler', () => {
  for (const nome of ['extrato.ofx', 'extrato.OFX', 'jan.csv', 'conta.pdf', 'x.qfx', 'y.xlsx']) {
    expect(problemaNoArquivo(falso(nome)), nome).toBeNull()
  }
})

it('recusa formato sem leitor, antes de subir e ocupar a rede', () => {
  expect(problemaNoArquivo(falso('virus.sh'))).toMatch(/formato/)
})

it('recusa arquivo grande demais', () => {
  expect(problemaNoArquivo(falso('gigante.pdf', LIMITE_BYTES + 1))).toMatch(/grande/)
})
