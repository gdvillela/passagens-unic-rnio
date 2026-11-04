"""Histórico de preços em SQLite. Cada varredura grava o menor preço visto por
(rota, data de ida, data de volta, fonte, dia da coleta)."""
import sqlite3
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS obs (
  origem TEXT, destino TEXT, tipo TEXT, ida TEXT, volta TEXT,
  preco REAL, fonte TEXT, cia TEXT, escalas INTEGER,
  dia_coleta TEXT,
  PRIMARY KEY (origem, destino, ida, volta, fonte, dia_coleta)
);
CREATE INDEX IF NOT EXISTS ix_rota ON obs(origem, destino, tipo, dia_coleta);
CREATE TABLE IF NOT EXISTS alertas (
  origem TEXT, destino TEXT, ida TEXT, volta TEXT, preco REAL, nivel TEXT, criado_em TEXT,
  PRIMARY KEY (origem, destino, ida, volta, preco)
);
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def gravar(self, ofertas, dia=None):
        dia = dia or datetime.now(timezone.utc).date().isoformat()
        rows = [(o.origem, o.destino, "RT" if o.volta else "OW", o.ida, o.volta or "",
                 o.preco, o.fonte, o.cia, o.escalas, dia) for o in ofertas]
        self.db.executemany("""
            INSERT INTO obs VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT DO UPDATE SET preco=MIN(preco, excluded.preco)""", rows)
        self.db.commit()

    def precos_rota(self, origem, destino, tipo, janela_dias, hoje=None, mes_ida=None):
        hoje = hoje or datetime.now(timezone.utc).date()
        desde = (hoje - timedelta(days=janela_dias)).isoformat()
        q = "SELECT preco FROM obs WHERE origem=? AND destino=? AND tipo=? AND dia_coleta>=?"
        args = [origem, destino, tipo, desde]
        if mes_ida:
            q += " AND substr(ida,6,2)=?"
            args.append(f"{int(mes_ida):02d}")
        return [r[0] for r in self.db.execute(q, args)]

    def ja_alertado(self, o):
        r = self.db.execute("SELECT 1 FROM alertas WHERE origem=? AND destino=? AND ida=? AND volta=? AND preco<=?",
                            (o.origem, o.destino, o.ida, o.volta or "", o.preco * 1.02)).fetchone()
        return r is not None

    def marcar_alerta(self, o, nivel):
        self.db.execute("INSERT OR IGNORE INTO alertas VALUES (?,?,?,?,?,?,?)",
                        (o.origem, o.destino, o.ida, o.volta or "", o.preco, nivel,
                         datetime.now(timezone.utc).isoformat()))
        self.db.commit()
