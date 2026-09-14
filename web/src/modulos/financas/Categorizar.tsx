/**
 * A tela que resolve as transações sem categoria.
 *
 * Decisão A da spec: o cliente manda o PADRÃO e o servidor recalcula o grupo. O
 * agrupamento nunca sai de `aplicacao/sugestoes.py` para cá — se saísse, a tela
 * poderia divergir do que o sistema entende por "grupo".
 *
 * O servidor devolve os fit_id que mudou, e é com eles que o desfazer volta
 * exatamente o que mudou, em vez de adivinhar.
 */
import { useEffect, useState } from 'react'

import { api } from '../../lib/api'
import { formatarMagnitude } from '../../lib/dinheiro'
import { aplicar, confirmar, progresso, reverter, type Grupo } from '../../lib/otimista'

type Aplicado = { fit_ids: string[]; regra_criada: boolean }

export function Categorizar() {
  const [grupos, setGrupos] = useState<Grupo[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [escolhas, setEscolhas] = useState<Record<string, string>>({})
  const [comRegra, setComRegra] = useState<Record<string, boolean>>({})
  const [desfazivel, setDesfazivel] = useState<
    { padrao: string; fit_ids: string[]; regra: string | null } | null
  >(null)

  useEffect(() => {
    api
      .get<Grupo[]>('/api/financas/sugestoes-de-regra?limite=30')
      .then(setGrupos)
      .catch((e) => setErro(e.message))
  }, [])

  async function aplicarGrupo(grupo: Grupo) {
    const categoria = (escolhas[grupo.padrao] ?? '').trim()
    if (!categoria) return
    const criarRegra = comRegra[grupo.padrao] ?? true

    // Otimista: a linha muda agora, sem esperar o servidor.
    setGrupos((atual) => (atual ? aplicar(atual, grupo.padrao, categoria) : atual))
    try {
      const resposta = await api.post<Aplicado>(
        '/api/financas/transacoes/categorizar-em-lote',
        { padrao: grupo.padrao, categoria, criar_regra: criarRegra },
      )
      setGrupos((atual) => (atual ? confirmar(atual, grupo.padrao) : atual))
      setDesfazivel({
        padrao: grupo.padrao,
        fit_ids: resposta.fit_ids,
        regra: resposta.regra_criada ? grupo.padrao : null,
      })
    } catch (e) {
      // Rollback VISÍVEL: a tela não pode ficar mostrando sucesso que o banco
      // não teve. O motivo vem da mensagem que o domínio escreveu.
      setGrupos((atual) =>
        atual ? reverter(atual, grupo.padrao, (e as Error).message) : atual,
      )
    }
  }

  async function desfazer() {
    if (!desfazivel) return
    await api.post('/api/financas/transacoes/desfazer-lote', {
      fit_ids: desfazivel.fit_ids,
      padrao_da_regra: desfazivel.regra,
    })
    setGrupos((atual) =>
      atual ? reverter(atual, desfazivel.padrao, 'desfeito por você') : atual,
    )
    setDesfazivel(null)
  }

  if (erro) return <p className="aviso">{erro}</p>
  if (!grupos) return <p style={{ color: 'var(--apagado)' }}>Carregando…</p>
  if (grupos.length === 0)
    return <p style={{ color: 'var(--apagado)' }}>Nada sem categoria por aqui.</p>

  const { resolvido, total } = progresso(grupos)

  return (
    <>
      <p style={{ color: 'var(--apagado)', marginTop: 0 }}>
        <strong className="dinheiro" style={{ color: 'var(--texto)' }}>
          {formatarMagnitude(resolvido)}
        </strong>{' '}
        de {formatarMagnitude(total)} resolvidos
      </p>

      <table className="grupos">
        <thead>
          <tr>
            <th>grupo</th>
            <th className="num">transações</th>
            <th className="num">valor</th>
            <th>categoria</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {grupos.map((grupo) => (
            <tr key={grupo.padrao} data-aplicado={grupo.aplicado ? 'sim' : undefined}>
              <td>
                <strong>{grupo.padrao}</strong>
                <div className="exemplo">{grupo.exemplo}</div>
              </td>
              <td className="num dinheiro">{grupo.ocorrencias}</td>
              <td className="num dinheiro">{formatarMagnitude(grupo.total_centavos)}</td>
              <td>
                {grupo.aplicado ? (
                  <span className={grupo.aplicado.confirmado ? 'ok' : 'pendente'}>
                    {grupo.aplicado.categoria}
                    {grupo.aplicado.confirmado ? '' : ' (salvando…)'}
                  </span>
                ) : (
                  <>
                    <input
                      id={`categoria-${grupo.padrao}`}
                      value={escolhas[grupo.padrao] ?? ''}
                      placeholder="escolher…"
                      onChange={(e) =>
                        setEscolhas({ ...escolhas, [grupo.padrao]: e.target.value })
                      }
                    />
                    <label className="regra">
                      <input
                        type="checkbox"
                        checked={comRegra[grupo.padrao] ?? true}
                        onChange={(e) =>
                          setComRegra({ ...comRegra, [grupo.padrao]: e.target.checked })
                        }
                      />
                      criar regra — pega {grupo.alcance} agora e os próximos extratos
                    </label>
                    {grupo.erro && <div className="falhou">não aplicou: {grupo.erro}</div>}
                  </>
                )}
              </td>
              <td>
                {!grupo.aplicado && (
                  <button onClick={() => aplicarGrupo(grupo)}>Aplicar</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {desfazivel && (
        <div className="desfazer">
          Aplicado a {desfazivel.fit_ids.length} transação(ões).
          <button onClick={desfazer}>Desfazer</button>
        </div>
      )}
    </>
  )
}
