from .base import Oferta, Provider
from .travelpayouts import Travelpayouts
from .serpapi import SerpApiGoogleFlights
from .duffel import Duffel
from .apify import ApifyGoogleFlights
from .mock import Mock

COLETORES = {"apify": ApifyGoogleFlights, "travelpayouts": Travelpayouts, "mock": Mock}
VALIDADORES = {"apify": ApifyGoogleFlights, "google_flights": SerpApiGoogleFlights, "duffel": Duffel}


def coletor_padrao():
    for nome in ("apify", "travelpayouts"):
        if COLETORES[nome]().disponivel():
            return nome
    return "travelpayouts"
