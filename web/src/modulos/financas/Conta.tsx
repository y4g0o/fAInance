/**
 * Saldo inicial da conta — o número que faz o saldo total deixar de ser ficção.
 */
import { useEffect, useState } from 'react'

import { api, ErroDaApi } from '../../lib/api'
import { motivoDoValorInvalido } from '../../lib/entrada'

export function Conta({ aoSalvar }: { aoSalvar: () => void }) {
  const [nome, setNome] = useState('conta')
  const [saldo, setSaldo] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [salvo, setSalvo] = useState<string | null>(null)
  const [contas, setContas] = useState<string[]>([])

  useEffect(() => {
    api
      .get<{ categoria: string }[]>('/api/financas/categorias')
      .then(() => setContas(['conta', 'manual']))
      .catch(() => setContas([]))
  }, [])

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault()
    const problema = motivoDoValorInvalido(saldo)
    if (problema) return setErro(problema)
    try {
      const r = await api.put<{ saldo_inicial_formatado: string }>(
        `/api/financas/contas/${encodeURIComponent(nome)}`,
        { saldo_inicial: saldo },
      )
      setSalvo(r.saldo_inicial_formatado)
      setErro(null)
      aoSalvar()
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : String(e))
    }
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <div className="campos">
        <label>
          conta
          <input id="conta-nome" value={nome} onChange={(e) => setNome(e.target.value)} list="contas-conhecidas" />
          <datalist id="contas-conhecidas">
            {contas.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </label>
        <label>
          saldo inicial
          <input id="conta-saldo" value={saldo} onChange={(e) => setSaldo(e.target.value)} placeholder="1.234,56" inputMode="decimal" />
        </label>
        <button type="submit">Salvar</button>
      </div>
      {erro && <p className="falhou">{erro}</p>}
      {salvo && <p className="ok">Saldo inicial definido em {salvo}.</p>}
      <p className="nota">
        É o saldo da conta <strong>na data da primeira transação importada</strong> — o
        sistema soma as movimentações a partir dele.
      </p>
    </form>
  )
}
