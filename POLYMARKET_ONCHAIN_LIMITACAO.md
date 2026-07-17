# ⚠️ Achado Crítico: Polymarket Não Suporta Buy/Sell Direto On-Chain

**Data:** 16 de julho de 2026
**Severidade:** 🔴 Bloqueante para o modelo atual de flash-loan arbitrage

## O que descobrimos

O contrato `FlashTrader.sol` usa uma interface `ICTFExchange` com `buyShares()`/
`sellShares()` que um contrato de terceiros poderia chamar diretamente, de forma
atômica, dentro do callback do flash loan — no mesmo padrão de um swap numa AMM
tipo Uniswap.

**Essa interface é fictícia.** Verificamos o endereço real do CTF Exchange da
Polymarket na Polygon (`0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`, confirmado
verificado no PolygonScan) e a documentação oficial do contrato
([Polymarket/ctf-exchange](https://github.com/Polymarket/ctf-exchange) e
[ctf-exchange-v2](https://github.com/Polymarket/ctf-exchange-v2)):

- A Polymarket funciona em modelo **"operator-driven order matching"**: ordens
  de compra/venda são assinadas **off-chain** (EIP-712) por quem quer comprar
  (taker) e por quem já tem uma ordem no book (maker).
- Um **operator autorizado da própria Polymarket** casa essas ordens e as
  submete on-chain via `matchOrders()`.
- Não existe nenhuma função pública tipo `buyShares(market, outcome, amount)`
  que um contrato qualquer possa chamar para comprar shares na hora, contra
  liquidez arbitrária. Isso foi removido até das versões mais antigas do
  contrato ("fillOrder/fillOrders — Removed in favor of the unified
  matchOrders entry point").

## Por que isso importa para o seu bot

O desenho atual (flash loan → compra shares → vende shares → repaga o
empréstimo, tudo numa transação atômica) **não é possível contra a Polymarket
real**, porque:

1. Comprar ou vender exige uma contraparte com ordem assinada e casada pelo
   operator da Polymarket — não é algo que seu contrato consiga fazer sozinho
   on-chain no meio de uma transação de flash loan.
2. Mesmo que o endereço do exchange no contrato estivesse certo, chamar
   `buyShares`/`sellShares` nele reverteria: essas funções não existem no ABI
   real do contrato.
3. Isso é diferente de arbitragem em uma AMM (Uniswap, por exemplo), onde o
   swap é atômico e determinístico — por isso flash loans funcionam tão bem
   ali, mas não se encaixam no modelo de order-matching da Polymarket.

## Caminho recomendado

Para automatizar operações reais na Polymarket, o caminho suportado
oficialmente é:

- Usar a **CLOB API** da Polymarket + SDK oficial em Python
  (`py-clob-client`) para criar, assinar e enviar ordens (limit ou market)
  com a sua própria carteira/capital.
- O operator da Polymarket casa e assenta a ordem on-chain — sua aplicação
  não precisa (e não consegue) fazer isso diretamente via contrato próprio.
- Isso significa abandonar o uso de **flash loan para a perna de execução na
  Polymarket** especificamente. Flash loans continuam sendo uma ferramenta
  válida para outras estratégias (ex: arbitragem entre DEXs tipo
  Uniswap/Sushiswap), só não se aplicam aqui.
- Nesse modelo, o bot opera com capital próprio (ex: os 500-3000 USDC que já
  estavam sendo cogitados), colocando ordens baseadas no score de sentimento,
  sujeito ao risco normal de execução de mercado (não é mais "arbitragem
  garantida" no sentido estrito).

## O que fizemos por enquanto

- Adicionamos um aviso direto no código-fonte do contrato (`FlashTrader.sol`)
  apontando que a interface é fictícia, para qualquer pessoa (ou IA) que ler o
  código no futuro não presumir que está pronta para produção.
- Mantivemos a estrutura de proteção de slippage (`minShares`/`minProceeds`)
  e o cálculo de lucro líquido após taxas dinâmicas, que continuam sendo
  boas práticas e serão reaproveitáveis se/quando migrarmos para uma
  estratégia de execução compatível (via `py-clob-client` ou uma AMM real).
- Removemos a constante `AAVE_POOL` que estava com endereço inválido e nunca
  era usada de fato (o Pool já é resolvido dinamicamente via
  `ADDRESSES_PROVIDER`, que é o padrão correto recomendado pela própria
  Aave).
