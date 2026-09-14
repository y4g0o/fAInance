/**
 * Conferência do arquivo antes de subir.
 *
 * O servidor confere de novo, e é ele quem decide — isto aqui só evita gastar
 * rede e tempo com um arquivo que já dá pra saber que será recusado. Os limites
 * são os mesmos do backend de propósito: divergir faria a tela prometer o que o
 * servidor nega.
 */
export const EXTENSOES = ['.ofx', '.qfx', '.csv', '.xlsx', '.pdf'] as const
export const LIMITE_BYTES = 10 * 1024 * 1024

export function problemaNoArquivo(arquivo: File): string | null {
  const nome = arquivo.name.toLowerCase()
  if (!EXTENSOES.some((ext) => nome.endsWith(ext))) {
    return `formato não suportado (aceito: ${EXTENSOES.join(', ')})`
  }
  if (arquivo.size > LIMITE_BYTES) {
    return `grande demais: passa de ${LIMITE_BYTES / (1024 * 1024)} MB`
  }
  return null
}
