"""Detecção de preços anômalos ("passagens unicórnio").

Para cada oferta compara o preço com até três bases, da mais forte para a mais fraca:
  1. Histórico próprio da rota (mesmo mês de ida se houver amostras; senão a rota toda).
     Usa mediana e MAD (robustos a outliers) -> desconto e z-score robusto.
  2. Faixa típica externa (Google Flights via SerpAPI), quando disponível.
  3. Comparação transversal: outras datas da mesma rota na mesma varredura
     (útil no começo, antes de existir histórico).
O nível final vem do maior desconto confiável; z-score baixo rebaixa o nível
(rota muito volátil não é 'unicórnio' só por estar abaixo da mediana).
"""
from dataclasses import dataclass
from statistics import median
from collections import defaultdict
from . import config


@dataclass
class Resultado:
    oferta: object
    nivel: str            # unicornio | otima | boa | normal
    desconto: float       # 0..1 vs. base
    base: float           # preço de referência (BRL)
    z: float
    fonte_base: str       # historico_mes | historico_rota | google | lote
    amostras: int

    def resumo(self):
        o = self.oferta
        return (f"{o.origem}->{o.destino} ({config.nome(o.destino)}, {config.regiao(o.destino)}) "
                f"ida {o.ida}{' volta ' + o.volta if o.volta else ''}: R$ {o.preco:,.0f} "
                f"vs base R$ {self.base:,.0f} (-{self.desconto:.0%}, z={self.z:.1f}, {self.fonte_base}, n={self.amostras})")


def _mad(xs, med):
    return median(abs(x - med) for x in xs)


def _stats(precos):
    med = median(precos)
    mad = _mad(precos, med) * 1.4826 or med * 0.05  # evita divisão por zero
    return med, mad


def _nivel(desconto):
    for n in ("unicornio", "otima", "boa"):
        if desconto >= config.LIMIAR[n]:
            return n
    return "normal"


_ORDEM = ["normal", "boa", "otima", "unicornio"]


def avaliar(ofertas, store, hoje=None):
    # base transversal: mediana por rota no próprio lote
    lote = defaultdict(list)
    for o in ofertas:
        lote[o.chave_rota()].append(o.preco)

    cache = {}
    res = []
    for o in ofertas:
        orig, dest, tipo = o.chave_rota()
        cand = []

        mes = o.ida[5:7]
        k = (orig, dest, tipo, mes)
        if k not in cache:
            h_mes = store.precos_rota(orig, dest, tipo, config.JANELA_DIAS, hoje, mes_ida=mes)
            h_rota = h_mes if len(h_mes) >= config.MIN_AMOSTRAS else \
                store.precos_rota(orig, dest, tipo, config.JANELA_DIAS, hoje)
            cache[k] = (h_mes, h_rota)
        h_mes, h_rota = cache[k]
        if len(h_mes) >= config.MIN_AMOSTRAS:
            cand.append(("historico_mes", h_mes))
        elif len(h_rota) >= config.MIN_AMOSTRAS:
            cand.append(("historico_rota", h_rota))

        if cand:
            nome_b, xs = cand[0]
            med, mad = _stats(xs)
            desc = 1 - o.preco / med
            z = (med - o.preco) / mad
            nivel = _nivel(desc)
            if z < config.Z_MIN and nivel != "normal":
                nivel = _ORDEM[max(_ORDEM.index(nivel) - 1, 0)]
            r = Resultado(o, nivel, desc, med, z, nome_b, len(xs))
        elif o.faixa_tipica:
            lo, hi = o.faixa_tipica
            ref = (lo + hi) / 2
            desc = 1 - o.preco / ref
            z = (lo - o.preco) / max((hi - lo) / 2, 1)
            r = Resultado(o, _nivel(desc), desc, ref, z, "google", 0)
        else:
            xs = lote[(orig, dest, tipo)]
            if len(xs) >= 5:
                med, mad = _stats(xs)
                desc = 1 - o.preco / med
                z = (med - o.preco) / mad
                nivel = _nivel(desc)
                # base fraca: exige um degrau a mais de evidência
                if nivel != "normal":
                    nivel = _ORDEM[max(_ORDEM.index(nivel) - 1, 0)]
                r = Resultado(o, nivel, desc, med, z, "lote", len(xs))
            else:
                r = Resultado(o, "normal", 0.0, o.preco, 0.0, "sem_base", len(xs))
        res.append(r)
    res.sort(key=lambda r: (-_ORDEM.index(r.nivel), -r.desconto))
    return res
