/**
 * "Posso comprar isso?" — os números, sem veredito.
 *
 * O sistema não decide por você: devolve parcela, juro embutido, quanto isso
 * come da sua folga e quantos meses de reserva você tem. A conversa sobre "isso
 * eu preciso" é sua.
 *
 * Informar o valor da parcela revela a taxa escondida — é assim que se descobre
 * que o "10x sem juros" cobra juro.
 */
import { useState } from 'react'

import { api, ErroDaApi } from '../../lib/api'
import { formatar } from '../../lib/dinheiro'
import { motivoDoValorInvalido } from '../../lib/entrada'

type Compra = {
  valor_centavos: number
  parcelas: number
  parcela_centavos: number
  custo_total_centavos: number
  juros_centavos: number
  taxa_mensal: number | null
  folga_mensal_centavos: number
  percentual_da_folga: number | null
  meses_de_reserva: number | null
  custo_basico_centavos: number
}

function paraCentavos(texto: string): number {
  return Math.round(Number(texto.replace(/\./g, '').replace(',', '.')) * 100)
}

export function Comprar() {
  const [valor, setValor] = useState('')
  const [parcelas, setParcelas] = useState('1')
  const [parcela, setParcela] = useState('')
  const [resposta, setResposta] = useState<Compra | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  async function simular(evento: React.FormEvent) {
    evento.preventDefault()
    const problema = motivoDoValorInvalido(valor)
    if (problema) return setErro(problema)

    const params = new URLSearchParams({
      valor_centavos: String(paraCentavos(valor)),
      parcelas: parcelas || '1',
    })
    if (parcela.trim()) params.set('parcela_centavos', String(paraCentavos(parcela)))

    try {
      setResposta(await api.get<Compra>(`/api/financas/pode-comprar?${params}`))
      setErro(null)
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : String(e))
      setResposta(null)
    }
  }

  return (
    <div className="formulario">
      <form className="campos" onSubmit={simular}>
        <label>
          valor à vista
          <input id="compra-valor" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="4.500,00" inputMode="decimal" />
        </label>
        <label>
          parcelas
          <input id="compra-parcelas" value={parcelas} onChange={(e) => setParcelas(e.target.value)} inputMode="numeric" style={{ minWidth: 80 }} />
        </label>
        <label>
          valor da parcela <span className="opcional">(opcional)</span>
          <input id="compra-parcela" value={parcela} onChange={(e) => setParcela(e.target.value)} placeholder="500,00" inputMode="decimal" />
        </label>
        <button type="submit">Calcular</button>
      </form>

      {erro && <p className="falhou">{erro}</p>}

      {resposta && (
        <>
          <div className="fichas" style={{ marginTop: 18 }}>
            <div className="ficha">
              <div className="ficha-rotulo">Parcela</div>
              <div className="ficha-valor dinheiro">{formatar(resposta.parcela_centavos)}</div>
              <div className="ficha-nota">{resposta.parcelas}x</div>
            </div>
            <div className="ficha">
              <div className="ficha-rotulo">Juro embutido</div>
              <div className="ficha-valor dinheiro">{formatar(resposta.juros_centavos)}</div>
              <div className="ficha-nota">
                {resposta.taxa_mensal !== null
                  ? `${(resposta.taxa_mensal * 100).toFixed(2)}% ao mês`
                  : 'sem taxa informada'}
              </div>
            </div>
            <div className="ficha">
              <div className="ficha-rotulo">Folga mensal</div>
              <div className="ficha-valor dinheiro">{formatar(resposta.folga_mensal_centavos)}</div>
              <div className="ficha-nota">
                {resposta.percentual_da_folga !== null
                  ? `a parcela come ${(resposta.percentual_da_folga * 100).toFixed(0)}%`
                  : 'sem base para comparar'}
              </div>
            </div>
            <div className="ficha">
              <div className="ficha-rotulo">Meses de reserva</div>
              <div className="ficha-valor dinheiro">
                {resposta.meses_de_reserva !== null
                  ? resposta.meses_de_reserva.toFixed(1)
                  : <span className="indisponivel">sem dado</span>}
              </div>
              <div className="ficha-nota">saldo ÷ custo básico</div>
            </div>
          </div>
          <p className="explica">
            São os fatos, não um conselho. O sistema <strong>não diz se você pode</strong> —
            essa decisão depende de coisas que ele não sabe.
          </p>
        </>
      )}
    </div>
  )
}
