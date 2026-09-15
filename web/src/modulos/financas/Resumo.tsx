/**
 * Resumo: os números que orientam decisão, sem gráfico.
 *
 * São valores únicos, não séries — a forma certa é o número grande, não a
 * barra. Gráfico aqui só ocuparia espaço para dizer o que o número já diz.
 *
 * Dado ausente aparece como ausente. Nada de zero fingindo saldo.
 */
import { useEffect, useState } from 'react'

import { api } from '../../lib/api'
import { formatar } from '../../lib/dinheiro'

type CustoBasico = {
  fixos_centavos: number
  variavel_centavos: number
  total_centavos: number
  meses_considerados: number
  fixos: [string, number][]
}
type Projecao = {
  mes: string
  dias_corridos: number
  dias_no_mes: number
  gasto_ate_agora_centavos: number
  fixos_pendentes_centavos: number
  projecao_centavos: number
  receita_prevista_centavos: number
} | null
type Saldo = { saldo_centavos: number }

function Numero({ rotulo, centavos, nota }: { rotulo: string; centavos: number | null; nota?: string }) {
  return (
    <div className="ficha">
      <div className="ficha-rotulo">{rotulo}</div>
      <div className="ficha-valor dinheiro">
        {centavos === null ? <span className="indisponivel">sem dado</span> : formatar(centavos)}
      </div>
      {nota && <div className="ficha-nota">{nota}</div>}
    </div>
  )
}

export function Resumo() {
  const [custo, setCusto] = useState<CustoBasico | null>(null)
  const [projecao, setProjecao] = useState<Projecao>(null)
  const [saldo, setSaldo] = useState<Saldo | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get<CustoBasico>('/api/financas/custo-basico').catch(() => null),
      api.get<Projecao>('/api/financas/projecao').catch(() => null),
      api.get<Saldo>('/api/financas/saldo').catch(() => null),
    ]).then(([c, p, s]) => {
      setCusto(c)
      setProjecao(p)
      setSaldo(s)
      setCarregando(false)
    })
  }, [])

  if (carregando) return <p className="carregando">Carregando…</p>

  return (
    <>
      <div className="fichas">
        <Numero rotulo="Saldo" centavos={saldo?.saldo_centavos ?? null} />
        <Numero
          rotulo="Custo básico por mês"
          centavos={custo?.total_centavos ?? null}
          nota={custo ? `${custo.meses_considerados} meses fechados` : undefined}
        />
        <Numero
          rotulo="Gastos fixos"
          centavos={custo?.fixos_centavos ?? null}
          nota={custo ? `${custo.fixos.length} reconhecidos` : undefined}
        />
        <Numero
          rotulo="Variável (mediana)"
          centavos={custo?.variavel_centavos ?? null}
          nota="mediana, não média"
        />
      </div>

      <h2 className="secao">Como o mês deve fechar</h2>
      {projecao ? (
        <div className="fichas">
          <Numero
            rotulo="Gasto projetado"
            centavos={projecao.projecao_centavos}
            nota={`dia ${projecao.dias_corridos} de ${projecao.dias_no_mes}`}
          />
          <Numero
            rotulo="Já gastou"
            centavos={projecao.gasto_ate_agora_centavos}
            nota="até agora"
          />
          <Numero
            rotulo="Fixos a cair"
            centavos={projecao.fixos_pendentes_centavos}
            nota="ainda neste mês"
          />
          <Numero
            rotulo="Receita prevista"
            centavos={projecao.receita_prevista_centavos}
          />
        </div>
      ) : (
        // Honestidade acima de completude: sem movimento, não há o que projetar.
        <p className="carregando">Nenhum movimento no mês corrente — nada a projetar.</p>
      )}
    </>
  )
}
