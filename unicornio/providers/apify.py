"""Google Flights via Apify (actor `lergassy/google-flights-api`, cobra ~US$ 0,20 por 1.000 linhas).

Dois usos:
  * Coletor amplo: modo `exploreAnywhere` lista os destinos mais baratos a partir de uma origem.
  * Validador: rota + data exatas, com a faixa de preço típica do Google e ~60 dias de histórico.

A página do actor não documenta todos os nomes de campos de saída, então o parser
aceita variações e salva a resposta bruta em `apify_bruto/` para ajuste fino.
Chave: console.apify.com -> Settings -> API & Integrations -> Personal API token.
Troque o actor com APIFY_ACTOR se quiser outro.
"""
import json
import os
from datetime import date, timedelta
from .base import Provider, Oferta, http_json
from .. import config

ACTOR = os.getenv("APIFY_ACTOR", "lergassy~google-flights-api")
URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def dia_do_mes(mes, hoje=None):
    """Escolhe o dia de ida para o mês. Muda a cada dia (passo 11 em 28 dias), então em
    4 semanas todos os dias de 1 a 28 são cobertos, sem aumentar o custo."""
    hoje = hoje or date.today()
    dia = (hoje.toordinal() * 11) % 28 + 1
    alvo = date(int(mes[:4]), int(mes[5:7]), dia)
    if alvo <= hoje + timedelta(days=2):          # mês atual: não buscar data passada
        alvo = hoje + timedelta(days=3)
    return alvo.isoformat()


def _pega(d, *chaves, default=None):
    """Primeiro valor não vazio entre várias chaves possíveis (aceita 'a.b' para aninhados)."""
    for c in chaves:
        v = d
        for parte in c.split("."):
            v = v.get(parte) if isinstance(v, dict) else None
            if v is None:
                break
        if v not in (None, "", []):
            return v
    return default


def _iata(v):
    if isinstance(v, dict):
        v = _pega(v, "iata", "code", "airportCode", "id")
    if isinstance(v, str) and len(v) == 3 and v.isalpha():
        return v.upper()
    return None


def _data(v):
    return v[:10] if isinstance(v, str) and len(v) >= 10 else None


def _faixa(d):
    f = _pega(d, "typicalPriceRange", "typical_price_range", "priceInsights.typicalPriceRange",
              "priceInsights.typical_price_range", "price_insights.typical_price_range")
    if isinstance(f, dict):
        f = [_pega(f, "low", "min", "from"), _pega(f, "high", "max", "to")]
    if isinstance(f, (list, tuple)) and len(f) == 2 and all(isinstance(x, (int, float)) for x in f):
        return tuple(f)
    return None


class ApifyGoogleFlights(Provider):
    nome = "apify_gflights"

    def __init__(self, token=None, salvar_bruto=True):
        self.token = token or os.getenv("APIFY_TOKEN")
        self.salvar_bruto = salvar_bruto

    def disponivel(self):
        return bool(self.token)

    def _rodar(self, entrada, rotulo):
        base = {"currency": config.MOEDA, "market": "BR", "language": "pt-BR",
                "includeSearchSummary": True, "includeRunSummary": False}
        corpo = {k: v for k, v in {**base, **entrada}.items() if v is not None}
        itens = http_json(URL.format(actor=ACTOR), params={"token": self.token, "timeout": 280},
                          body=corpo, timeout=300)
        if self.salvar_bruto:
            os.makedirs("apify_bruto", exist_ok=True)
            with open(f"apify_bruto/{date.today()}_{rotulo}.json", "w", encoding="utf-8") as f:
                json.dump(itens, f, ensure_ascii=False, indent=1)
        return itens if isinstance(itens, list) else []

    def _oferta(self, it, origem, destino=None, ida=None, volta=None, faixa=None):
        preco = _pega(it, "price", "lowestPrice", "minPrice", "totalPrice")
        if isinstance(preco, dict):
            preco = _pega(preco, "amount", "value", "total")
        dest = destino or _iata(_pega(it, "destination", "destinationCode", "destinationAirport",
                                      "arrivalAirport", "airportCode", "iata", "arrival_id"))
        ida = ida or _data(_pega(it, "departureDate", "outboundDate", "startDate", "date", "departAt"))
        if not (isinstance(preco, (int, float)) and dest and ida):
            return None
        volta = volta or _data(_pega(it, "returnDate", "endDate", "inboundDate"))
        return Oferta(
            origem=origem, destino=config.cidade(dest), ida=ida, volta=volta,
            preco=float(preco), fonte=self.nome,
            cia=str(_pega(it, "airline", "airlines", default="")),
            escalas=int(_pega(it, "stops", default=0) or 0),
            duracao_min=int(_pega(it, "totalDurationMinutes", "durationMinutes", default=0) or 0),
            link=_pega(it, "googleFlightsUrl", "url", "link", default=""),
            faixa_tipica=_faixa(it) or faixa,
            extra={"price_level": _pega(it, "priceLevel"),
                   "cidade": _pega(it, "city", "destinationCity"), "pais": _pega(it, "country")},
        )

    def buscar(self, origem, destino=None, mes=None, ida=None, volta=None):
        origem_aero = config.aeroporto(origem)
        if destino and ida:
            itens = self._rodar({"origin": origem_aero, "destination": config.aeroporto(destino),
                                 "departureDate": ida, "returnDate": volta, "sortBy": "price",
                                 "maxResults": 30}, f"{origem}-{destino}-{ida}")
            resumo = next((i for i in itens if i.get("type") == "search"), {})
            faixa = _faixa(resumo)
            voos = [i for i in itens if i.get("type") not in ("search", "notice", "calendar_day")]
            out = [self._oferta(i, origem, destino, ida, volta, faixa) for i in voos]
        else:
            entrada = {"origin": origem_aero, "exploreAnywhere": True, "maxDestinations": 200}
            if mes:
                entrada["departureDate"] = dia_do_mes(mes) if len(mes) == 7 else mes
            itens = self._rodar(entrada, f"{origem}-explore-{mes or 'flex'}")
            out = [self._oferta(i, origem) for i in itens if i.get("type") not in ("search", "notice")]
        out = [o for o in out if o]
        if itens and not out:
            print(f"  aviso: Apify devolveu {len(itens)} linhas mas nenhuma foi entendida; "
                  f"veja apify_bruto/ e me mande um exemplo")
        return out
