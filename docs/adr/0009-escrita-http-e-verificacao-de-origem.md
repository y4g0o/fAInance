# ADR 0009 — Escrita via HTTP e verificação de origem

**Data:** 2026-09-14 · **Estado:** Aceita

## Contexto

Até o v0.2.3 a API só lia, e rodar sem autenticação em loopback era seguro: um
site aberto no navegador não consegue ler resposta de outra origem.

Com endpoints de escrita isso muda. Qualquer página aberta no mesmo navegador
pode disparar `POST` para `127.0.0.1:8000`. Ela não lê a resposta, mas **grava** —
apagar categorias, inserir lançamentos, bagunçar o banco. É CSRF clássico, e o
fato de o servidor ser local não protege de nada.

## Decisão

1. **Toda requisição que escreve exige `Origin` da própria interface.** Sem
   `Origin`, ou com origem diferente, a resposta é 403.
2. **Sem senha.** O usuário continua abrindo `localhost` e usando.

## Por quê `Origin`, e não token ou login

`Origin` é preenchido pelo navegador e uma página **não consegue forjá-lo**.
Custa ~15 linhas, nada para o usuário, e fecha exatamente o vetor que existe.
Senha em painel local de um usuário só seria atrito diário sem ameaça
correspondente — a máquina já está destrancada se alguém está nela.

## Requisição sem `Origin` também é recusada

Não há cliente legítimo sem navegador a proteger: a CLI fala com o banco direto,
nunca com o HTTP. Abrir exceção para "cliente não-browser" reabriria o vetor
para qualquer coisa que não mande o cabeçalho.

## Consequências

- Todo teste de HTTP passa por um cliente que simula navegador. Quando o
  middleware entrou, 15 testes quebraram de uma vez — era ele funcionando.
- O upload de extrato trouxe `python-multipart`, que a 0007 tinha evitado. Lá era
  para não instalar dependência por um formulário de um campo; aqui é upload de
  arquivo binário, que é o caso de uso dela.
- **Continua fora:** `Host` forjado, CORS explícito, limites de taxa. Estão na
  revisão de segurança pedida para depois desta etapa.
