/**
 * Cliente HTTP da API local.
 *
 * Mesma origem sempre: o navegador manda `Origin` sozinho, que é o que a API
 * exige para aceitar escrita (ADR 0009). Não há token nem login — a proteção é
 * a origem, e ela não é problema nosso aqui.
 */
export class ErroDaApi extends Error {
  status: number

  constructor(status: number, mensagem: string) {
    super(mensagem)
    this.status = status
  }
}

async function pedir<T>(caminho: string, init?: RequestInit): Promise<T> {
  const resposta = await fetch(caminho, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!resposta.ok) {
    // A API devolve `detail` com a mensagem que o domínio escreveu. Ela é escrita
    // para humano — repassar é melhor do que inventar texto genérico aqui.
    const corpo = await resposta.json().catch(() => ({}))
    throw new ErroDaApi(resposta.status, corpo.detail ?? `Falhou (${resposta.status})`)
  }
  return resposta.json() as Promise<T>
}

export const api = {
  get: <T,>(caminho: string) => pedir<T>(caminho),
  post: <T,>(caminho: string, corpo: unknown) =>
    pedir<T>(caminho, { method: 'POST', body: JSON.stringify(corpo) }),
  put: <T,>(caminho: string, corpo: unknown) =>
    pedir<T>(caminho, { method: 'PUT', body: JSON.stringify(corpo) }),
  patch: <T,>(caminho: string, corpo: unknown) =>
    pedir<T>(caminho, { method: 'PATCH', body: JSON.stringify(corpo) }),
}

export type Saude = { ok: boolean; versao: string; modulos: string[] }
