/**
 * Onde o dinheiro vai: categorias ranqueadas e candidatos a corte.
 *
 * Barra horizontal de uma cor só, ordenada por magnitude — a identidade está no
 * rótulo, não na cor. Colorir cada categoria exigiria uma paleta categórica e
 * não acrescentaria informação nenhuma.
 */
import { useEffect, useState } from 'react'

import { api } from '../../lib/api'
import { formatarMagnitude } from '../../lib/dinheiro'
import { escala, fatias } from '../../lib/grafico'

type Categoria = { categoria: string; total_centavos: number }
type Corte = { descricao: string; tipo: string; mensal_centavos: number; anual_centavos: number }

export function Analise() {
  const [categorias, setCategorias] = useState<Categoria[] | null>(null)
  const [cortes, setCortes] = useState<Corte[] | null>(null)

  useEffect(() => {
    api.get<Categoria[]>('/api/financas/categorias').then(setCategorias).catch(() => setCategorias([]))
    api.get<Corte[]>('/api/financas/onde-cortar?limite=8').then(setCortes).catch(() => setCortes([]))
  }, [])

  if (!categorias || !cortes) return <p className="carregando">Carregando…</p>

  const dados = fatias(categorias.map((c) => ({ rotulo: c.categoria, centavos: c.total_centavos })))
  const largura = escala(dados.map((d) => d.centavos))

  return (
    <>
      <h2 className="secao">Gasto por categoria</h2>
      {dados.length === 0 ? (
        <p className="carregando">Sem gasto categorizado ainda.</p>
      ) : (
        <ul className="barras">
          {dados.map((d) => (
            <li key={d.rotulo}>
              <span className="barra-rotulo">{d.rotulo}</span>
              <span className="barra-trilho">
                <span
                  className="barra-marca"
                  style={{ width: `${largura(d.centavos)}%` }}
                  title={`${d.rotulo}: ${formatarMagnitude(d.centavos)} (${d.percentual.toFixed(0)}%)`}
                />
              </span>
              <span className="barra-valor dinheiro">{formatarMagnitude(d.centavos)}</span>
              <span className="barra-parte">{d.percentual.toFixed(0)}%</span>
            </li>
          ))}
        </ul>
      )}

      <h2 className="secao">Onde cortaria mais</h2>
      <p className="explica">
        Ranqueado pelo impacto <strong>anual</strong> — é o número que convence. O sistema
        não julga o que é essencial: essa conversa é sua.
      </p>
      {cortes.length === 0 ? (
        <p className="carregando">Ainda não há meses fechados suficientes para ranquear.</p>
      ) : (
        <div className="scroll">
          <table className="tabela">
            <thead>
              <tr>
                <th>o quê</th>
                <th>tipo</th>
                <th className="num">por mês</th>
                <th className="num">por ano</th>
              </tr>
            </thead>
            <tbody>
              {cortes.map((c) => (
                <tr key={`${c.tipo}-${c.descricao}`}>
                  <td>{c.descricao}</td>
                  <td className="tipo">{c.tipo}</td>
                  <td className="num dinheiro">{formatarMagnitude(c.mensal_centavos)}</td>
                  <td className="num dinheiro forte">{formatarMagnitude(c.anual_centavos)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
