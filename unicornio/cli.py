"""Linha de comando.

  python -m unicornio demo                  # sem chaves: simula 120 dias de histórico e roda a detecção
  python -m unicornio scan --origens SAO,RIO --meses 6
  python -m unicornio scan --fonte mock     # pipeline completo com dados falsos
"""
import argparse
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

from . import config
from .store import Store
from .detector import avaliar
from .providers import COLETORES, VALIDADORES, Mock, coletor_padrao


def proximos_meses(n, hoje=None):
    hoje = hoje or date.today()
    y, m = hoje.year, hoje.month
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def coletar(fonte, origens, meses, log):
    ofertas = []
    for org in origens:
        if isinstance(fonte, Mock):
            ofertas += fonte.buscar(org)
            continue
        for mes in meses:
            try:
                got = fonte.buscar(org, destino=None, mes=mes)
                log(f"  {fonte.nome} {org} {mes}: {len(got)} ofertas")
                ofertas += got
            except Exception as e:  # uma rota falhar não derruba a varredura
                log(f"  ERRO {fonte.nome} {org} {mes}: {e}")
    return ofertas


def validar(resultados, log):
    """Revalida candidatos fortes em fonte ao vivo. Devolve (validados, descartados)."""
    vals = [V() for V in VALIDADORES.values()]
    vals = [v for v in vals if v.disponivel()]
    if not vals:
        for r in resultados:
            r.oferta.extra["validado"] = None
        return resultados, []
    ok, fora = [], []
    for r in resultados:
        o = r.oferta
        vivo = None
        for v in vals:
            try:
                got = v.buscar(o.origem, o.destino, ida=o.ida, volta=o.volta)
                got = [g for g in got if not g.extra.get("moeda")]
                if got:
                    vivo = min(got, key=lambda g: g.preco)
                    break
            except Exception as e:
                log(f"  validação {v.nome} falhou: {e}")
        if vivo is None:
            o.extra["validado"] = None
            ok.append(r)
        elif vivo.preco <= o.preco * 1.15:
            o.extra["validado"] = f"{vivo.fonte}: R$ {vivo.preco:,.0f}"
            if vivo.faixa_tipica:
                o.extra["faixa_google"] = vivo.faixa_tipica
            ok.append(r)
        else:
            o.extra["validado"] = False
            fora.append(r)
            log(f"  descartado (preço sumiu): {o.origem}->{o.destino} {o.ida} agora R$ {vivo.preco:,.0f}")
    return ok, fora


def telegram(texto):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": texto, "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)
    return True


EMOJI = {"unicornio": "🦄", "otima": "🔥", "boa": "👍"}


def relatorio_html(resultados, path):
    linhas = []
    for r in resultados:
        o = r.oferta
        val = o.extra.get("validado")
        val_txt = "não validado" if val is None else html.escape(str(val))
        link = f'<a href="{html.escape(o.link)}">abrir</a>' if o.link else ""
        linhas.append(
            f"<tr class='{r.nivel}'><td>{EMOJI.get(r.nivel,'')} {r.nivel}</td><td>{o.origem}→{o.destino}</td>"
            f"<td>{html.escape(config.nome(o.destino))}</td><td>{html.escape(config.regiao(o.destino))}</td>"
            f"<td>{o.ida}{' / ' + o.volta if o.volta else ''}</td><td>R$ {o.preco:,.0f}</td>"
            f"<td>R$ {r.base:,.0f}</td><td>-{r.desconto:.0%}</td><td>{r.z:.1f}</td><td>{r.fonte_base} (n={r.amostras})</td>"
            f"<td>{html.escape(o.cia)}</td><td>{o.escalas}</td><td>{val_txt}</td><td>{link}</td></tr>")
    doc = f"""<!doctype html><meta charset="utf-8"><title>Passagens unicórnio</title>
<style>body{{font-family:system-ui;margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{padding:4px 8px;border-bottom:1px solid #ddd;font-size:14px;text-align:left}}
.unicornio{{background:#f3e8ff}}.otima{{background:#fff4e0}}</style>
<h1>Passagens unicórnio — {date.today().isoformat()}</h1>
<table><tr><th>Nível</th><th>Rota</th><th>Destino</th><th>Região</th><th>Datas</th><th>Preço</th>
<th>Base</th><th>Desconto</th><th>z</th><th>Base usada</th><th>Cia</th><th>Escalas</th><th>Validação</th><th></th></tr>
{''.join(linhas)}</table>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def rodar(fonte, origens, meses, store, saida, hoje=None, log=print, nivel_min="otima"):
    ofertas = coletar(fonte, origens, proximos_meses(meses, hoje), log)
    log(f"{len(ofertas)} ofertas coletadas")
    res = avaliar(ofertas, store, hoje)          # avalia ANTES de gravar (não se compara consigo mesmo)
    store.gravar(ofertas, dia=hoje.isoformat() if hoje else None)
    ordem = ["boa", "otima", "unicornio"]
    fortes = [r for r in res if r.nivel in ordem[ordem.index(nivel_min):]]
    fortes, _ = validar(fortes, log)
    boas = [r for r in res if r.nivel == "boa" and r not in fortes]
    final = fortes + boas
    for r in fortes:
        if not store.ja_alertado(r.oferta):
            msg = f"{EMOJI[r.nivel]} {r.resumo()}\n{r.oferta.link}"
            if telegram(msg):
                log("  alerta enviado no Telegram")
            store.marcar_alerta(r.oferta, r.nivel)
    if saida:
        relatorio_html(final, saida + ".html")
        with open(saida + ".json", "w", encoding="utf-8") as f:
            json.dump([{**r.oferta.to_dict(), "nivel": r.nivel, "desconto": round(r.desconto, 3),
                        "base": round(r.base, 2), "z": round(r.z, 2), "fonte_base": r.fonte_base}
                       for r in final], f, ensure_ascii=False, indent=1)
    return final


def main(argv=None):
    p = argparse.ArgumentParser(prog="unicornio")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="varre APIs, grava histórico e detecta anomalias")
    s.add_argument("--origens", default=",".join(config.ORIGENS_PADRAO))
    s.add_argument("--meses", type=int, default=6, help="quantos meses à frente varrer")
    s.add_argument("--fonte", default=None, choices=list(COLETORES), help="padrão: apify se houver APIFY_TOKEN, senão travelpayouts")
    s.add_argument("--db", default=config.DB_PATH)
    s.add_argument("--saida", default="relatorio")
    s.add_argument("--nivel-min", default="otima", choices=["boa", "otima", "unicornio"])
    d = sub.add_parser("demo", help="simula histórico com dados falsos e roda a detecção")
    d.add_argument("--dias", type=int, default=120)
    d.add_argument("--db", default="demo.db")
    d.add_argument("--saida", default="relatorio_demo")
    a = p.parse_args(argv)

    if a.cmd == "scan":
        a.fonte = a.fonte or coletor_padrao()
        fonte = COLETORES[a.fonte]()
        if not fonte.disponivel():
            sys.exit(f"Fonte {a.fonte} sem chave. Defina APIFY_TOKEN ou TRAVELPAYOUTS_TOKEN, ou use --fonte mock / demo.")
        final = rodar(fonte, a.origens.split(","), a.meses, Store(a.db), a.saida, nivel_min=a.nivel_min)
    else:
        if os.path.exists(a.db):
            os.remove(a.db)
        store = Store(a.db)
        mock = Mock(seed=42)
        hoje = date.today()
        print(f"Simulando {a.dias} dias de coleta diária...")
        for i in range(a.dias, 0, -1):
            dia = hoje - timedelta(days=i)
            ofs = []
            for org in config.ORIGENS_PADRAO:
                ofs += mock.buscar(org, hoje=dia)
            store.gravar(ofs, dia=dia.isoformat())
        mock.prob = 0.02  # hoje tem mais 'tarifas-erro' para a demo ficar interessante
        final = rodar(mock, config.ORIGENS_PADRAO, 1, store, a.saida, hoje=hoje, log=lambda *_: None)

    for r in final[:25]:
        print(f"{EMOJI.get(r.nivel, '  ')} {r.resumo()}")
    print(f"\n{len(final)} ofertas relevantes. Relatório: {a.saida}.html / .json")


if __name__ == "__main__":
    main()
