"""Origens, destinos e limiares padrão."""
import os

# Aeroportos/cidades por região. Códigos de cidade (SAO, RIO) agrupam aeroportos.
BRASIL = {
    "SAO": "São Paulo", "RIO": "Rio de Janeiro", "BSB": "Brasília", "CNF": "Belo Horizonte",
    "SSA": "Salvador", "REC": "Recife", "FOR": "Fortaleza", "NAT": "Natal", "MCZ": "Maceió",
    "JPA": "João Pessoa", "AJU": "Aracaju", "SLZ": "São Luís", "THE": "Teresina",
    "BEL": "Belém", "MAO": "Manaus", "MCP": "Macapá", "BVB": "Boa Vista", "PVH": "Porto Velho",
    "RBR": "Rio Branco", "PMW": "Palmas", "GYN": "Goiânia", "CGB": "Cuiabá", "CGR": "Campo Grande",
    "CWB": "Curitiba", "FLN": "Florianópolis", "POA": "Porto Alegre", "VIX": "Vitória",
    "IGU": "Foz do Iguaçu", "FEN": "Fernando de Noronha", "BPS": "Porto Seguro",
}

EXTERIOR = {
    "America do Sul": {"BUE": "Buenos Aires", "SCL": "Santiago", "LIM": "Lima", "BOG": "Bogotá",
                       "MVD": "Montevidéu", "CUZ": "Cusco", "ASU": "Assunção"},
    "America do Norte e Central": {"MIA": "Miami", "ORL": "Orlando", "NYC": "Nova York",
                                   "LAX": "Los Angeles", "CUN": "Cancún", "MEX": "Cidade do México",
                                   "PTY": "Panamá", "PUJ": "Punta Cana", "YTO": "Toronto"},
    "Europa": {"LIS": "Lisboa", "OPO": "Porto", "MAD": "Madri", "BCN": "Barcelona", "PAR": "Paris",
               "ROM": "Roma", "MIL": "Milão", "LON": "Londres", "AMS": "Amsterdã",
               "FRA": "Frankfurt", "ZRH": "Zurique"},
    "Africa": {"JNB": "Joanesburgo", "CPT": "Cidade do Cabo", "CMN": "Casablanca",
               "LAD": "Luanda", "CAI": "Cairo"},
    "Asia e Oriente Medio": {"DXB": "Dubai", "DOH": "Doha", "IST": "Istambul", "TYO": "Tóquio",
                             "BKK": "Bangkok", "SIN": "Singapura", "DEL": "Nova Délhi"},
    "Oceania": {"SYD": "Sydney", "MEL": "Melbourne", "AKL": "Auckland"},
}


def regiao(iata: str) -> str:
    if iata in BRASIL:
        return "Brasil"
    for reg, cidades in EXTERIOR.items():
        if iata in cidades:
            return reg
    return "Outros"


def nome(iata: str) -> str:
    if iata in BRASIL:
        return BRASIL[iata]
    for cidades in EXTERIOR.values():
        if iata in cidades:
            return cidades[iata]
    return iata


def todos_destinos(excluir=()):
    dest = list(BRASIL) + [c for cs in EXTERIOR.values() for c in cs]
    return [d for d in dest if d not in excluir]


ORIGENS_PADRAO = os.getenv("UNICORNIO_ORIGENS", "SAO,RIO,BSB").split(",")
DB_PATH = os.getenv("UNICORNIO_DB", "precos.db")
MOEDA = "BRL"

# Limiares de detecção (desconto vs. mediana histórica da rota)
LIMIAR = {
    "unicornio": 0.55,   # >= 55% abaixo da mediana
    "otima": 0.40,
    "boa": 0.25,
}
Z_MIN = 2.5              # z-score robusto mínimo (mediana/MAD)
MIN_AMOSTRAS = 15        # observações históricas mínimas para confiar na base
JANELA_DIAS = 180        # quanto histórico considerar

# Aeroporto -> código de cidade (para juntar o histórico de fontes diferentes)
AEROPORTO_CIDADE = {
    "GRU": "SAO", "CGH": "SAO", "VCP": "SAO", "GIG": "RIO", "SDU": "RIO", "CNF": "CNF", "PLU": "CNF",
    "EZE": "BUE", "AEP": "BUE", "JFK": "NYC", "EWR": "NYC", "LGA": "NYC", "MCO": "ORL",
    "CDG": "PAR", "ORY": "PAR", "FCO": "ROM", "CIA": "ROM", "MXP": "MIL", "LIN": "MIL",
    "LHR": "LON", "LGW": "LON", "STN": "LON", "NRT": "TYO", "HND": "TYO", "YYZ": "YTO",
    "DWC": "DXB", "SAW": "IST", "DMK": "BKK", "MEX": "MEX", "NLU": "MEX",
}
# Código de cidade -> aeroporto principal (Google Flights prefere aeroporto)
CIDADE_AEROPORTO = {"SAO": "GRU", "RIO": "GIG", "BUE": "EZE", "NYC": "JFK", "ORL": "MCO",
                    "PAR": "CDG", "ROM": "FCO", "MIL": "MXP", "LON": "LHR", "TYO": "NRT", "YTO": "YYZ"}


def cidade(iata: str) -> str:
    return AEROPORTO_CIDADE.get(iata, iata)


def aeroporto(iata: str) -> str:
    return CIDADE_AEROPORTO.get(iata, iata)
