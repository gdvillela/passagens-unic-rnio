from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import urllib.request
import urllib.parse
import urllib.error


@dataclass
class Oferta:
    origem: str
    destino: str
    ida: str                      # YYYY-MM-DD
    volta: Optional[str]          # None = só ida
    preco: float                  # BRL
    fonte: str
    cia: str = ""
    escalas: int = 0
    duracao_min: int = 0
    link: str = ""
    coletado_em: str = ""         # ISO; quando a fonte viu esse preço
    # referência externa (ex.: faixa típica do Google Flights), se a fonte fornecer
    faixa_tipica: Optional[tuple] = None
    extra: dict = field(default_factory=dict)

    def chave_rota(self):
        return (self.origem, self.destino, "RT" if self.volta else "OW")

    def to_dict(self):
        return asdict(self)


class Provider:
    nome = "base"

    def disponivel(self) -> bool:
        return True

    def buscar(self, origem, destino=None, mes=None, ida=None, volta=None):
        """Retorna lista de Oferta. destino=None significa 'qualquer destino', se a fonte permitir."""
        raise NotImplementedError


def http_json(url, params=None, headers=None, body=None, timeout=30):
    if params:
        url = url + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detalhe}") from None
