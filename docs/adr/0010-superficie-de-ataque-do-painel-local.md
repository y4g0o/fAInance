# ADR 0010 — Superfície de ataque de um painel local sem senha

**Data:** 2026-09-15 · **Estado:** Aceita · **Complementa:** [ADR 0009](0009-escrita-http-e-verificacao-de-origem.md)

## Contexto

A revisão de segurança pedida ao fim do P1 encontrou uma falha **explorável** na
proteção que a 0009 tinha introduzido, além de três exposições menores. Vale
registrar porque a lição se repete: *"é local, então é seguro"* é falso.

## O que estava errado

**1. Verificação de origem burlável por DNS rebinding (crítico).**
A 0009 comparava `Origin` com `Host`. Num ataque de DNS rebinding os **dois são
do atacante**: um domínio dele resolve para 127.0.0.1, o navegador envia `Host:
site-malicioso.com` e `Origin: http://site-malicioso.com`, e a comparação fecha.

Verificado contra o servidor real antes do conserto: a requisição respondeu 201
e **gravou uma transação no banco**.

Correção: o `Host` é conferido contra uma lista fixa de loopback ANTES de
qualquer comparação. O servidor só aceita bind em loopback, então qualquer outro
`Host` é forjado por definição.

**2. Extratos legíveis por qualquer usuário da máquina.**
O banco (`600`) e os backups (`700`) já estavam certos; a pasta de extratos era
criada com o umask padrão e ficava `775`. Extrato bancário em arquivo `644` é
dado sensível aberto. Agora a pasta é `700` e os arquivos `600`.

**3. Limite de upload que não limitava.**
O tamanho era conferido DEPOIS de `read()` do arquivo inteiro. Agora a leitura é
em pedaços e para no limite.

**4. Metabase publicado na rede inteira.**
`ports: "3000:3000"` expõe em 0.0.0.0. O **setup inicial do Metabase não tem
autenticação**: qualquer um na mesma rede abriria a tela de criação de conta e
depois leria as finanças. Agora é `127.0.0.1:3000:3000`.

## O que foi verificado e está correto

- Bind fora de loopback recusado sem escape hatch, com teste.
- SQL parametrizado em todo lugar. As duas exceções são DDL de view com nomes
  vindos de constantes do próprio código, não de entrada do usuário.
- Nome de arquivo enviado é reduzido ao basename — verificado que o Starlette
  entrega `../../x.ofx` com os pontos intactos, então a guarda faz trabalho real.
- Banco e backups com permissão restrita.
- Sem CORS configurado: o navegador bloqueia leitura cross-origin por padrão.

## O que continua fora

- **Sem autenticação.** É um usuário numa máquina destrancada; senha seria atrito
  diário sem ameaça correspondente. Revisar se o acesso remoto entrar na pauta.
- **Sem limite de taxa.** Não há ameaça de força bruta sem login.
- **Conteúdo do extrato não é validado contra malícia** (só contra incoerência).
  Os leitores usam bibliotecas de terceiros sobre arquivo que o usuário mesmo
  baixou do banco; um PDF hostil é risco dessas bibliotecas, não deste código.

## Lição

As quatro falhas vieram do mesmo raciocínio: *"roda em 127.0.0.1, então está
protegido"*. Loopback protege contra a rede, não contra o navegador do próprio
usuário nem contra outros processos da máquina — e é por essas duas frestas que
tudo aqui entrou.
