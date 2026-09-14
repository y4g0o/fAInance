/**
 * Lançamento manual: dinheiro vivo, PIX, o que não vem em extrato.
 *
 * O valor é sempre MAGNITUDE positiva e quem decide o sinal é o tipo — mesma
 * defesa do backend, e a razão de o campo não aceitar número negativo.
 */
import { useState } from 'react'

import { api, ErroDaApi } from '../../lib/api'
import { formatar } from '../../lib/dinheiro'
import { motivoDoValorInvalido } from '../../lib/entrada'

type Lancado = { valor_centavos: number; descricao: string; categoria: string | null; inserida: boolean }

const HOJE = new Date().toISOString().slice(0, 10)

export function Lancar({ aoLancar }: { aoLancar: () => void }) {
  const [descricao, setDescricao] = useState('')
  const [valor, setValor] = useState('')
  const [tipo, setTipo] = useState('despesa')
  const [data, setData] = useState(HOJE)
  const [erro, setErro] = useState<string | null>(null)
  const [feito, setFeito] = useState<Lancado | null>(null)
  const [salvando, setSalvando] = useState(false)

  const problemaNoValor = valor ? motivoDoValorInvalido(valor) : null

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault()
    const problema = motivoDoValorInvalido(valor)
    if (problema) return setErro(problema)
    if (!descricao.trim()) return setErro('descreva o lançamento')

    setSalvando(true)
    setErro(null)
    try {
      const resposta = await api.post<Lancado>('/api/financas/lancamentos', {
        descricao: descricao.trim(),
        valor,
        tipo,
        data,
      })
      setFeito(resposta)
      setDescricao('')
      setValor('')
      aoLancar()
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : String(e))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <div className="campos">
        <label>
          descrição
          <input id="lanc-descricao" value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="cafe" />
        </label>
        <label>
          valor
          <input id="lanc-valor" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="7,50" inputMode="decimal" />
        </label>
        <label>
          tipo
          <select id="lanc-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="despesa">saiu</option>
            <option value="receita">entrou</option>
          </select>
        </label>
        <label>
          data
          <input id="lanc-data" type="date" value={data} onChange={(e) => setData(e.target.value)} />
        </label>
        <button type="submit" disabled={salvando || !!problemaNoValor}>
          {salvando ? 'salvando…' : 'Lançar'}
        </button>
      </div>

      {problemaNoValor && <p className="falhou">{problemaNoValor}</p>}
      {erro && <p className="falhou">{erro}</p>}
      {feito && (
        <p className={feito.inserida ? 'ok' : 'pendente'}>
          {feito.inserida
            ? `Lançado: ${formatar(feito.valor_centavos)} — ${feito.descricao}`
            : 'Já existia um lançamento idêntico nesse dia; nada foi inserido.'}
        </p>
      )}
      <p className="nota">
        Use para o que <strong>não</strong> vem em extrato. Lançar aqui algo que depois chega
        no OFX conta o gasto duas vezes.
      </p>
    </form>
  )
}
