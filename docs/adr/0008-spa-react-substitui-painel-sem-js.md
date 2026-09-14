# ADR 0008 — SPA React substitui o painel sem JavaScript

**Data:** 2026-09-14 · **Estado:** Aceita · **Substitui:** [ADR 0007](0007-painel-sem-javascript.md)

## Contexto

A 0007 decidiu zero JavaScript: gráfico em SVG do servidor e formulário HTML com
POST/Redirect/GET. A decisão estava **certa para o que existia**: um painel de
leitura, com um gráfico e uma interação.

O que mudou não foi a tecnologia, foi o papel da interface. O usuário pediu que
**tudo** passe a ser possível pela aplicação — importar extrato, corrigir saldo,
lançar à mão e categorizar centenas de transações. A tela deixou de ser um
relatório e virou o jeito principal de operar o sistema.

Com escrita em lote, o custo de "toda ação recarrega a página" deixa de ser
imperceptível: categorizar dez grupos seriam dez recarregamentos, cada um
perdendo posição de rolagem e contexto. E a exigência de atualização otimista com
desfazer não tem como ser cumprida com formulário e redirecionamento.

## Decisão

SPA em **React + Vite + TypeScript**, servida pelo próprio FastAPI a partir de
`web_dist/` versionado no git. O painel Jinja continua vivo até o fim do P2.

## Por quê React, e não o SolidJS que a spec do v0.2 previa

Critério decisivo foi manutenção, não desempenho: o projeto é de uma pessoa só,
e a interface será mantida com assistência de IA. React tem, de longe, mais
material — o que significa menos tempo parado quando algo quebrar daqui a dois
anos. SolidJS seria mais leve e mais rápido; não compensa a solidão quando o bug
aparece.

## Custo aceito

`node_modules` é **a única parte do sistema que exige manutenção contínua**. O
resto é Python puro que roda igual daqui a dez anos. Isso contraria a carta
original do projeto, e foi aceito conscientemente porque a alternativa era uma
interface que não faz o que se pede dela.

## Gatilho de arrependimento

Se em um ano o `npm install` estiver quebrando sozinho, ou uma major do React
exigir reescrita, voltar para HTML servido pelo servidor — o backend não muda,
porque a API já é a mesma para os dois.

## Consequências

- Duas interfaces convivem durante a transição (`/` Jinja, `/app` SPA).
- O teste de arquitetura ganhou uma terceira fronteira: `web/src/shell/` não pode
  citar módulo nenhum.
- Dinheiro no front é só formatação: o backend manda centavos inteiros, porque
  `0.1 + 0.2 !== 0.3` em JavaScript.
