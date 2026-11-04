"""Fonte simulada para testar o pipeline sem chaves de API.

Gera preços plausíveis por rota (base por distância/região + sazonalidade + ruído)
e injeta algumas tarifas-erro de vez em quando.
"""
import random
import hashlib
from datetime import date, timedelta
from .base import Provider, Oferta
from .. import config

BASE_REGIAO = {
    "Brasil": 650, "America do Sul": 1700, "America do Norte e Central": 3600,
    "Europa": 4800, "Africa": 5600, "Asia e Oriente Medio": 6800, "Oceania": 8200, "Outros": 4000,
}


class Mock(Provider):
    nome = "mock"

    def __init__(self, seed=None, prob_unicornio=0.004):
        self.rng = random.Random(seed)
        self.prob = prob_unicornio

    def _base(self, o, d):
        h = int(hashlib.md5(f"{o}{d}".encode()).hexdigest()[:6], 16) / 0xFFFFFF
        return BASE_REGIAO[config.regiao(d)] * (0.75 + 0.6 * h)

    def preco(self, o, d, ida: date):
        p = self._base(o, d)
        if ida.month in (1, 7, 12):
            p *= 1.25
        p *= self.rng.lognormvariate(0, 0.12)
        if self.rng.random() < self.prob:
            p *= self.rng.uniform(0.25, 0.45)   # tarifa-erro / promo relâmpago
        return round(p, 2)

    def buscar(self, origem, destino=None, mes=None, ida=None, volta=None, hoje=None):
        hoje = hoje or date.today()
        destinos = [destino] if destino else config.todos_destinos(excluir={origem})
        out = []
        for d in destinos:
            for _ in range(3):
                dia = hoje + timedelta(days=self.rng.randint(14, 300))
                out.append(Oferta(origem=origem, destino=d, ida=dia.isoformat(), volta=None,
                                  preco=self.preco(origem, d, dia), fonte=self.nome,
                                  cia=self.rng.choice(["LA", "G3", "AD", "TP", "AF", "IB", "CM"]),
                                  escalas=self.rng.choice([0, 0, 1, 1, 2]),
                                  coletado_em=hoje.isoformat()))
        return out
