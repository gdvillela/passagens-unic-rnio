# Passagens unicórnio

Ferramenta que varre APIs de voos partindo do Brasil (para outros estados e para todos os continentes), guarda o histórico de preços de cada rota e avisa quando aparece uma tarifa muito abaixo do normal.

Python 3.10+, só biblioteca padrão (sem `pip install`).

## Como rodar

```bash
# 1) Sem nenhuma chave: simula 120 dias de histórico e mostra a detecção funcionando
python -m unicornio demo

# 2) Com chave da Apify (Google Flights) — usada automaticamente se existir
export APIFY_TOKEN=...          # console.apify.com > Settings > API & Integrations
python -m unicornio scan --origens SAO,RIO,BSB --meses 6

# ou com a Travelpayouts (grátis)
export TRAVELPAYOUTS_TOKEN=...
python -m unicornio scan --fonte travelpayouts

# Opcional: validação ao vivo e alertas
export SERPAPI_KEY=...          # Google Flights (faixa de preço típica + confirma o preço)
export DUFFEL_TOKEN=...         # preço ao vivo direto das companhias
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
```

O `scan` gera `relatorio.html` e `relatorio.json` e grava tudo em `precos.db` (SQLite). Rode 1 a 4 vezes por dia (no GitHub isso já está pronto em `.github/workflows/scan.yml`, que grava o histórico e o relatório na pasta `dados/`). O histórico próprio é o que torna a detecção boa: depois de 2 a 3 semanas de coleta, cada rota já tem base sólida.

## Arquitetura

```
 Coletores (varredura ampla, barata)      Validadores (ao vivo, por candidato)
   Travelpayouts: origem -> QUALQUER        Google Flights (SerpAPI)
   destino, mês a mês, preços em cache      Duffel
            │                                       ▲
            ▼                                       │ só ofertas "ótima"/"unicórnio"
   Detector de anomalias  ──────────────────────────┘
     base 1: histórico próprio da rota (SQLite)                 │
     base 2: faixa típica do Google Flights                     ▼
     base 3: outras datas da mesma rota no lote        Alerta (Telegram) + relatório
```

1. **Coleta**: uma chamada por origem e por mês traz centenas de destinos. 3 origens x 6 meses = 18 chamadas por varredura.
2. **Detecção** (`unicornio/detector.py`): para cada oferta calcula a mediana e o desvio robusto (MAD) dos preços da rota nos últimos 180 dias, de preferência só para o mesmo mês de ida (por causa da sazonalidade: julho e dezembro são caros).
   - `desconto = 1 - preço / mediana`
   - `z = (mediana - preço) / (1,4826 x MAD)` (quantos "desvios típicos" abaixo do normal)
   - Níveis: 🦄 unicórnio >= 55% de desconto, 🔥 ótima >= 40%, 👍 boa >= 25%. Se `z < 2,5`, cai um nível (rota muito instável não conta). Com menos de 15 amostras, usa a faixa do Google Flights ou as outras datas do lote, e cai um nível por ser base fraca.
   - Avalia antes de gravar, para a oferta não entrar na própria base.
3. **Validação**: preços em cache podem ter até 48 h. Antes de alertar, o candidato é buscado de novo em fonte ao vivo; se o preço subiu mais de 15%, é descartado.
4. **Alerta**: Telegram, sem repetir a mesma tarifa.

Os limiares ficam em `unicornio/config.py`, junto com as listas de capitais brasileiras e destinos por continente.

## APIs (situação em novembro de 2026)

| API | Custo | Histórico de preços | Papel aqui |
|---|---|---|---|
| **Travelpayouts / Aviasales Data API** | Grátis (cadastro de afiliado) | Preços em cache das buscas dos últimos dias; aceita "qualquer destino" | Coletor principal |
| **Google Flights via Apify** (actor `lergassy/google-flights-api`) | ~US$ 0,20 por 1.000 linhas; uma varredura de 3 origens x 6 meses traz ~1.250 linhas, cerca de US$ 0,25 | Sim: faixa típica e ~60 dias de histórico da rota | Coletor (modo "qualquer destino") e validador |
| **Google Flights via SerpAPI** | Plano grátis ~100 buscas/mês; pagos a partir de ~US$ 75/mês | Sim: `price_insights` traz faixa típica e histórico da rota | Validador + base externa |
| **Duffel** | Busca grátis; cobra por reserva | Não | Validador ao vivo |
| Amadeus Self-Service | **Encerrado em julho de 2026** | — | Não usar |
| Kiwi Tequila | Fechado para novos cadastros desde 2024 | — | Não usar |
| Skyscanner | Só para parceiros aprovados | — | Futuro, se conseguir acesso |

Valores aproximados; confira nos sites antes de assinar.

### Observação sobre a Apify

O actor escolhido é novo (poucos usuários) e a página dele não documenta todos os nomes de campos do modo "qualquer destino". O leitor aceita várias variações e salva a resposta bruta em `apify_bruto/`. Se aparecer o aviso "nenhuma linha foi entendida", basta mandar um desses arquivos para ajustar. Para usar outro actor, defina `APIFY_ACTOR`.

## Próximos passos sugeridos

- Ida e volta (hoje o foco é só ida, que é o que mais aparece como tarifa-erro).
- Calendário de datas por rota (endpoint `grouped_prices`) para achar a data mais barata do mês.
- Milhas: comparar com tabelas de resgate (Smiles, LATAM Pass, TudoAzul).
- Painel web com gráfico do histórico de cada rota.
