/**
 * Lista de alertas. Determinística de ponta a ponta: cada número aqui saiu de
 * SQL ou de função pura no backend, nunca de modelo de linguagem (ADR 0002).
 */
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import { dispensarLocalmente, type Insight } from './alertas'

const ROTULO: Record<string, string> = {
  alerta: 'alerta',
  atencao: 'atenção',
  info: 'info',
}

export function Alertas() {
  const [insights, setInsights] = useState<Insight[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<Insight[]>('/api/insights?status=novo')
      .then(setInsights)
      .catch((e) => setErro(e.message))
  }, [])

  async function dispensar(id: number) {
    const antes = insights
    setInsights((atual) => (atual ? dispensarLocalmente(atual, id) : atual))
    try {
      await api.patch(`/api/insights/${id}/status`, { status: 'dispensado' })
    } catch (e) {
      // Rollback visível: se o servidor recusou, o alerta volta pra lista.
      setInsights(antes)
      setErro((e as Error).message)
    }
  }

  if (erro) return <p className="aviso">{erro}</p>
  if (!insights) return <p className="carregando">Carregando…</p>
  if (insights.length === 0)
    return <p className="carregando">Nenhum alerta novo.</p>

  return (
    <ul className="alertas">
      {insights.map((i) => (
        <li key={i.id} data-severidade={i.severidade}>
          <div>
            <span className="selo">{ROTULO[i.severidade] ?? i.severidade}</span>
            <span className="origem">{i.modulo}</span>
          </div>
          <p>{i.titulo}</p>
          <button onClick={() => dispensar(i.id)}>Dispensar</button>
        </li>
      ))}
    </ul>
  )
}
