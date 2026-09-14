/**
 * A moldura do PersonalOS: navegação, tema e layout.
 *
 * REGRA DE ARQUITETURA: nada aqui pode citar um módulo pelo nome. As seções vêm
 * de `/api/saude` e as telas vêm do registro passado por props — quem sabe QUAL
 * módulo tem QUAL tela é a composição, nunca a moldura. Há teste que falha o
 * build se a palavra de um módulo aparecer nesta pasta.
 *
 * É o mesmo contrato que o painel Jinja já respeita (ADR 0006), e é o que faz um
 * módulo novo entrar sem tocar aqui.
 */
import { useEffect, useState } from 'react'

import { api, type Saude } from '../lib/api'
import { Alertas } from './Alertas'
import './tema.css'

const ALERTAS = '__alertas__'

export type Registro = Record<string, { titulo: string; Tela: () => React.ReactNode }>

function usarTema() {
  const [tema, setTema] = useState<'escuro' | 'claro'>(
    () => (localStorage.getItem('tema') as 'escuro' | 'claro') ?? 'escuro',
  )
  useEffect(() => {
    document.documentElement.dataset.tema = tema
    localStorage.setItem('tema', tema)
  }, [tema])
  return { tema, alternar: () => setTema(tema === 'escuro' ? 'claro' : 'escuro') }
}

export function Shell({ registro }: { registro: Registro }) {
  const [saude, setSaude] = useState<Saude | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [ativo, setAtivo] = useState<string | null>(null)
  const { tema, alternar } = usarTema()

  useEffect(() => {
    api
      .get<Saude>('/api/saude')
      .then((s) => {
        setSaude(s)
        setAtivo((atual) => atual ?? s.modulos[0] ?? null)
      })
      .catch((e) => setErro(e.message))
  }, [])

  // Sem dado é sem dado: nada de esqueleto fingindo conteúdo que não existe.
  if (erro) {
    return (
      <div className="conteudo">
        <p className="aviso">Não consegui falar com o PersonalOS: {erro}</p>
      </div>
    )
  }

  const modulos = saude?.modulos ?? []
  // "Alertas" é seção do kernel, não módulo: todo módulo produz insights, e esta
  // lista só os apresenta. Por isso ela é fixa, e as demais vêm da API.
  const emAlertas = ativo === ALERTAS
  const atual = ativo && !emAlertas ? registro[ativo] : undefined

  return (
    <div className="aplicacao">
      <nav className="barra">
        <div className="marca">
          PersonalOS
          <div className="versao">{saude ? `v${saude.versao}` : 'conectando…'}</div>
        </div>
        {modulos.map((nome) => (
          <button
            key={nome}
            onClick={() => setAtivo(nome)}
            aria-current={nome === ativo ? 'page' : undefined}
          >
            {registro[nome]?.titulo ?? nome}
          </button>
        ))}
        <button onClick={() => setAtivo(ALERTAS)} aria-current={emAlertas ? 'page' : undefined}>
          Alertas
        </button>
        <div className="rodape-barra">
          <button onClick={alternar}>{tema === 'escuro' ? 'Tema claro' : 'Tema escuro'}</button>
        </div>
      </nav>
      <main className="conteudo">
        {emAlertas ? (
          <>
            <h1>Alertas</h1>
            <Alertas />
          </>
        ) : atual ? (
          <>
            <h1>{atual.titulo}</h1>
            <atual.Tela />
          </>
        ) : (
          <p className="aviso">Nenhum módulo ativo neste PersonalOS.</p>
        )}
      </main>
    </div>
  )
}
