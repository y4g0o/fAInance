/**
 * Arrastar o extrato na tela — o caminho que substitui copiar arquivo pra uma
 * pasta e rodar comando.
 *
 * O envio é multipart, então NÃO passa pelo cliente JSON de lib/api: o navegador
 * precisa montar o boundary sozinho. Origin continua indo automaticamente, que é
 * o que a API exige para aceitar escrita.
 */
import { useRef, useState } from 'react'

import { EXTENSOES, problemaNoArquivo } from '../../lib/arquivos'

type Resultado = { novas: number; arquivos: string[] }

export function Importar({ aoImportar }: { aoImportar: () => void }) {
  const [sobre, setSobre] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [feito, setFeito] = useState<Resultado | null>(null)
  const entrada = useRef<HTMLInputElement>(null)

  async function enviar(lista: FileList | null) {
    if (!lista || lista.length === 0) return
    const arquivos = Array.from(lista)

    const recusado = arquivos.map((a) => [a, problemaNoArquivo(a)] as const).find(([, p]) => p)
    if (recusado) {
      setErro(`${recusado[0].name}: ${recusado[1]}`)
      return
    }

    setEnviando(true)
    setErro(null)
    setFeito(null)
    try {
      const corpo = new FormData()
      for (const arquivo of arquivos) corpo.append('arquivos', arquivo)
      const resposta = await fetch('/api/financas/extratos', { method: 'POST', body: corpo })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) {
        // A mensagem vem do leitor: "a soma não fecha com os saldos declarados"
        // é muito mais útil que "erro ao importar".
        throw new Error(dados.detail ?? `falhou (${resposta.status})`)
      }
      setFeito(dados as Resultado)
      aoImportar()
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="formulario">
      <div
        className={`solta${sobre ? ' sobre' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setSobre(true)
        }}
        onDragLeave={() => setSobre(false)}
        onDrop={(e) => {
          e.preventDefault()
          setSobre(false)
          void enviar(e.dataTransfer.files)
        }}
        onClick={() => entrada.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') entrada.current?.click()
        }}
        role="button"
        tabIndex={0}
        aria-label="Solte os extratos aqui ou clique para escolher"
      >
        <strong>{enviando ? 'Importando…' : 'Solte os extratos aqui'}</strong>
        <span>ou clique para escolher — {EXTENSOES.join(', ')}</span>
        <input
          id="entrada-extratos"
          ref={entrada}
          type="file"
          multiple
          accept={EXTENSOES.join(',')}
          hidden
          onChange={(e) => void enviar(e.target.files)}
        />
      </div>

      {erro && <p className="falhou">{erro}</p>}
      {feito && (
        <p className={feito.novas > 0 ? 'ok' : 'pendente'}>
          {feito.novas > 0
            ? `${feito.novas} transação(ões) nova(s) de ${feito.arquivos.length} arquivo(s).`
            : 'Nada novo: essas transações já estavam no banco.'}
        </p>
      )}

      <p className="nota">
        Reenviar o mesmo extrato é seguro — a deduplicação por identificador do banco
        ignora o que já entrou. Em PDF, se a soma não fechar com os saldos declarados
        no próprio documento, o arquivo é <strong>recusado</strong> em vez de entrar
        errado.
      </p>
    </div>
  )
}
