"""Duffel (preços ao vivo direto das companhias; gratuito para buscar em modo teste,
cobra por reserva). Bom para confirmar que a tarifa existe agora, antes de alertar.
Não traz histórico. Chave: duffel.com -> Access token.
"""
import os
from .base import Provider, Oferta, http_json

URL = "https://api.duffel.com/air/offer_requests?return_offers=true"


class Duffel(Provider):
    nome = "duffel"

    def __init__(self, token=None):
        self.token = token or os.getenv("DUFFEL_TOKEN")

    def disponivel(self):
        return bool(self.token)

    def buscar(self, origem, destino=None, mes=None, ida=None, volta=None):
        if not (destino and ida):
            return []
        slices = [{"origin": origem, "destination": destino, "departure_date": ida}]
        if volta:
            slices.append({"origin": destino, "destination": origem, "departure_date": volta})
        js = http_json(URL, headers={
            "Authorization": f"Bearer {self.token}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
        }, body={"data": {"slices": slices, "passengers": [{"type": "adult"}],
                          "cabin_class": "economy", "max_connections": 2}}, timeout=60)
        out = []
        for o in js.get("data", {}).get("offers", []):
            if o.get("total_currency") != "BRL":
                # Duffel cota na moeda da cia; conversão fica para o chamador
                o_extra = {"moeda": o.get("total_currency")}
            else:
                o_extra = {}
            segs = o["slices"][0]["segments"]
            out.append(Oferta(
                origem=origem, destino=destino, ida=ida, volta=volta,
                preco=float(o["total_amount"]), fonte=self.nome,
                cia=o.get("owner", {}).get("name", ""),
                escalas=len(segs) - 1, extra=o_extra,
            ))
        return out
