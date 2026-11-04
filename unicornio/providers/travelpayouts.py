"""Travelpayouts / Aviasales Data API (gratuita, preços em cache das buscas de usuários).

Melhor fonte para varredura ampla: permite 'qualquer destino' a partir de uma origem
e devolve preços dos últimos dias. Os preços são cache (podem ter até ~48h), então
toda oferta forte deve ser revalidada numa fonte ao vivo (SerpAPI ou Duffel).
Chave: crie conta em travelpayouts.com -> Developers -> API token.
"""
import os
from .base import Provider, Oferta, http_json
from .. import config

URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class Travelpayouts(Provider):
    nome = "travelpayouts"

    def __init__(self, token=None, marker=None):
        self.token = token or os.getenv("TRAVELPAYOUTS_TOKEN")
        self.marker = marker or os.getenv("TRAVELPAYOUTS_MARKER", "")

    def disponivel(self):
        return bool(self.token)

    def buscar(self, origem, destino=None, mes=None, ida=None, volta=None, one_way=True):
        params = {
            "origin": origem,
            "destination": destino,
            "departure_at": ida or mes,          # YYYY-MM ou YYYY-MM-DD
            "return_at": volta,
            "one_way": "true" if one_way and not volta else "false",
            "currency": "brl",
            "sorting": "price",
            "limit": 1000,
            "token": self.token,
        }
        js = http_json(URL, params)
        out = []
        for d in js.get("data", []):
            out.append(Oferta(
                origem=d.get("origin", origem),
                destino=config.cidade(d["destination"]),
                ida=d["departure_at"][:10],
                volta=(d.get("return_at") or "")[:10] or None,
                preco=float(d["price"]),
                fonte=self.nome,
                cia=d.get("airline", ""),
                escalas=int(d.get("transfers", 0) or 0),
                duracao_min=int(d.get("duration", 0) or 0),
                link=("https://www.aviasales.com" + d["link"] + (f"&marker={self.marker}" if self.marker else ""))
                if d.get("link") else "",
            ))
        return out
