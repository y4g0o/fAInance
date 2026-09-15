/**
 * Telas de finanças. Esta pasta PODE saber tudo sobre dinheiro — é a moldura que
 * não pode.
 */
import { useCallback, useEffect, useState } from 'react'

import { api } from '../../lib/api'
import { formatar } from '../../lib/dinheiro'
import { Categorizar } from './Categorizar'
import { Analise } from './Analise'
import { Comprar } from './Comprar'
import { Conta } from './Conta'
import { Fluxo } from './Fluxo'
import { Fixos } from './Fixos'
import { Importar } from './Importar'
import { Lancar } from './Lancar'
import { Resumo } from './Resumo'
import './financas.css'

type Saldo = { saldo_centavos: number }

const ABAS = [
  { id: 'resumo', rotulo: 'Resumo' },
  { id: 'analise', rotulo: 'Onde vai o dinheiro' },
  { id: 'fluxo', rotulo: 'Fluxo mensal' },
  { id: 'comprar', rotulo: 'Posso comprar?' },
  { id: 'fixos', rotulo: 'Gastos fixos' },
  { id: 'importar', rotulo: 'Importar extrato' },
  { id: 'categorizar', rotulo: 'Categorizar' },
  { id: 'lancar', rotulo: 'Lançar' },
  { id: 'conta', rotulo: 'Saldo da conta' },
] as const

export function TelaFinancas() {
  const [saldo, setSaldo] = useState<Saldo | null>(null)
  const [aba, setAba] = useState<string>('resumo')

  const recarregarSaldo = useCallback(() => {
    api.get<Saldo>('/api/financas/saldo').then(setSaldo).catch(() => setSaldo(null))
  }, [])

  useEffect(recarregarSaldo, [recarregarSaldo])

  return (
    <>
      {/* Sem dado é sem dado: nada de zero fingindo saldo. */}
      <p className="dinheiro saldo">
        {saldo ? (
          formatar(saldo.saldo_centavos)
        ) : (
          <span className="indisponivel">saldo indisponível</span>
        )}
      </p>

      <div className="abas">
        {ABAS.map((a) => (
          <button key={a.id} onClick={() => setAba(a.id)} aria-current={aba === a.id ? 'page' : undefined}>
            {a.rotulo}
          </button>
        ))}
      </div>

      {aba === 'resumo' && <Resumo />}
      {aba === 'analise' && <Analise />}
      {aba === 'fluxo' && <Fluxo />}
      {aba === 'comprar' && <Comprar />}
      {aba === 'fixos' && <Fixos />}
      {aba === 'importar' && <Importar aoImportar={recarregarSaldo} />}
      {aba === 'categorizar' && <Categorizar />}
      {aba === 'lancar' && <Lancar aoLancar={recarregarSaldo} />}
      {aba === 'conta' && <Conta aoSalvar={recarregarSaldo} />}
    </>
  )
}
