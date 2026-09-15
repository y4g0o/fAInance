/**
 * Fluxo mensal: o que entrou e o que saiu, mês a mês.
 *
 * Entrada sobe, saída desce a partir de uma linha zero. A posição é a
 * codificação principal — verde e vermelho separam mal para quem tem daltonismo
 * vermelho-verde (medido: ΔE 6,1 em deuteranopia), então cor aqui é reforço, e o
 * que de fato distingue é a direção da barra e o rótulo.
 */
import { useEffect, useState } from 'react'

import { api } from '../../lib/api'
import { formatar, formatarMagnitude } from '../../lib/dinheiro'
import { escalaFluxo, resultado, type MesFluxo } from '../../lib/grafico'

type LinhaApi = { mes: string; receitas_centavos: number; despesas_centavos: number }

export function Fluxo() {
  const [meses, setMeses] = useState<MesFluxo[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<LinhaApi[]>('/api/financas/fluxo-mensal')
      .then((linhas) =>
        setMeses(
          linhas.map((l) => ({
            mes: l.mes,
            entradas: Math.abs(l.receitas_centavos),
            saidas: Math.abs(l.despesas_centavos),
          })),
        ),
      )
      .catch((e) => setErro(e.message))
  }, [])

  if (erro) return <p className="aviso">{erro}</p>
  if (!meses) return <p className="carregando">Carregando…</p>
  if (meses.length === 0) return <p className="carregando">Nenhum mês com movimento.</p>

  const altura = escalaFluxo(meses)

  return (
    <>
      <div className="legenda">
        <span className="chave">
          <span className="amostra entrada" /> entrou
        </span>
        <span className="chave">
          <span className="amostra saida" /> saiu
        </span>
      </div>

      <div className="scroll">
        <div className="fluxo" style={{ minWidth: `${meses.length * 56}px` }}>
          {meses.map((m) => {
            const sobra = resultado(m)
            return (
              <div key={m.mes} className="coluna">
                <div className="acima">
                  <span
                    className="haste entrada"
                    style={{ height: `${altura(m.entradas)}%` }}
                    title={`${m.mes} · entrou ${formatarMagnitude(m.entradas)}`}
                  />
                </div>
                <div className="zero" />
                <div className="abaixo">
                  <span
                    className="haste saida"
                    style={{ height: `${altura(m.saidas)}%` }}
                    title={`${m.mes} · saiu ${formatarMagnitude(m.saidas)}`}
                  />
                </div>
                <div className={`sobra dinheiro ${sobra < 0 ? 'negativa' : ''}`}>
                  {formatar(sobra)}
                </div>
                <div className="rotulo-mes">{m.mes.slice(5)}/{m.mes.slice(2, 4)}</div>
              </div>
            )
          })}
        </div>
      </div>
      <p className="explica">
        Entrada e saída usam a <strong>mesma escala</strong> — escalas separadas fariam
        uma saída menor parecer maior que uma entrada maior. O número embaixo é a sobra
        do mês.
      </p>
      <p className="explica">
        Este gráfico mostra <strong>tudo que passou pela conta</strong>, inclusive
        transferência entre as suas próprias contas. Por isso ele não bate com “Onde vai
        o dinheiro”, que conta só consumo — são perguntas diferentes: o que{' '}
        <em>movimentou</em> e o que você <em>gastou</em>.
      </p>
    </>
  )
}
