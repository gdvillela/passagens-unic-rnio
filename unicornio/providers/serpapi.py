"""Google Flights via SerpAPI (paga por busca; plano grátis ~100 buscas/mês).

Ponto forte: devolve `price_insights` com a faixa de preço típica e o histórico
recente da rota segundo o Google. Isso dá uma base histórica pronta desde o dia 1,
sem esperar acumular dados próprios. Usado como validador de candidatos.
Chave: serpapi.com -> API key.
"""
import os
from .base import Provider, Oferta, http_json

URL = "https://serpapi.com/search.json"


class SerpApiGoogleFlights(Provider):
    nome = "google_flights"

    def __init__(self, key=None):
        self.key = key or os.getenv("SERPAPI_KEY")

    def disponivel(self):
        return bool(self.key)

    def buscar(self, origem, destino=None, mes=None, ida=None, volta=None):
        if not (destino and ida):
            return []  # Google Flights exige rota e data exatas
        params = {
            "engine": "google_flights",
            "departure_id": origem,
            "arrival_id": destino,
            "outbound_date": ida,
            "return_date": volta,
            "type": 1 if volta else 2,
            "currency": "BRL",
            "hl": "pt-BR",
            "gl": "br",
            "api_key": self.key,
        }
        js = http_json(URL, params)
        ins = js.get("price_insights", {}) or {}
        faixa = tuple(ins["typical_price_range"]) if ins.get("typical_price_range") else None
        out = []
        for grupo in ("best_flights", "other_flights"):
            for f in js.get(grupo, []) or []:
                if "price" not in f:
                    continue
                trechos = f.get("flights", [])
                out.append(Oferta(
                    origem=origem, destino=destino, ida=ida, volta=volta,
                    preco=float(f["price"]), fonte=self.nome,
                    cia=", ".join(sorted({t.get("airline", "") for t in trechos})),
                    escalas=max(len(trechos) - 1, 0),
                    duracao_min=int(f.get("total_duration", 0) or 0),
                    link=js.get("search_metadata", {}).get("google_flights_url", ""),
                    faixa_tipica=faixa,
                    extra={"price_level": ins.get("price_level"),
                           "price_history": ins.get("price_history", [])},
                ))
        return out
