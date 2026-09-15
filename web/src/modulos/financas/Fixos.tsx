/**
 * O que o sistema aprendeu sozinho — e como discordar.
 *
 * Existe porque o aprendizado ERRA de um jeito específico: compra recorrente de
 * marketplace atende ao critério (3 meses, valor parecido) e vira "fixo". Sem
 * esta tela o usuário só descobre quando um alerta estranho aparece, e a única
 * correção ficava no terminal.
 */
import { useEffect, useState } from 'react'

import { api } from '../../lib/api'
import { formatarMagnitude } from '../../lib/dinheiro'

type Fixo = {
  chave: string
  descricao_exemplo: string
  valor_mediano_centavos: number
  meses: number
  ultima_data: string
}

export function Fixos() {
  const [fixos, setFixos] = useState<Fixo[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    api.get<Fixo[]>('/api/financas/fixos').then(setFixos).catch((e) => setErro(e.message))
  }, [])

  async function esquecer(chave: string) {
    const antes = fixos
    setFixos((atual) => atual?.filter((f) => f.chave !== chave) ?? null)
    try {
      await api.post(`/api/financas/fixos/${encodeURIComponent(chave)}/esquecer`, {})
    } catch (e) {
      setFixos(antes) // rollback visível: se o servidor recusou, ele volta
      setErro((e as Error).message)
    }
  }

  if (erro) return <p className="aviso">{erro}</p>
  if (!fixos) return <p className="carregando">Carregando…</p>
  if (fixos.length === 0)
    return <p className="carregando">Nenhum gasto fixo aprendido ainda (precisa de 3 meses).</p>

  return (
    <>
      <p className="explica">
        Aprendidos do histórico: aparecem em ≥3 meses com valor estável. Compra que se
        repete por acaso também cai aqui — <strong>esquecer</strong> tira de vez, e a
        decisão sobrevive à próxima importação.
      </p>
      <div className="scroll">
        <table className="tabela">
          <thead>
            <tr>
              <th>gasto</th>
              <th className="num">mediana</th>
              <th className="num">meses</th>
              <th>última vez</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {fixos.map((f) => (
              <tr key={f.chave}>
                <td>{f.descricao_exemplo}</td>
                <td className="num dinheiro">{formatarMagnitude(f.valor_mediano_centavos)}</td>
                <td className="num">{f.meses}</td>
                <td>{f.ultima_data}</td>
                <td>
                  <button onClick={() => esquecer(f.chave)}>Não é fixo</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
