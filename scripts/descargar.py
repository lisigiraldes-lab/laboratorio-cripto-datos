"""Descarga diaria de datos públicos para el Laboratorio cripto.

Solo usa endpoints públicos y gratuitos, sin API keys. Escribe en data/latest/:
  universo.csv      top 60 por volumen (CoinGecko), sin stablecoins ni tokens envueltos
  cierres.csv       cierres diarios (400 días) de cada moneda del universo con par USDT
  verificacion.csv  precio actual en dos fuentes y su diferencia porcentual
  global.json       dominancia de BTC y capitalización total
  funding.csv       funding de perpetuos de Binance (si está disponible)
  dolar_cripto.json USDT/ARS por exchange (CriptoYa)
  estado.json       qué se pudo descargar y qué falló
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "latest")
UA = {"User-Agent": "laboratorio-cripto-datos/1.0", "Accept": "application/json"}
EXCLUIR = {
    "usdt", "usdc", "dai", "fdusd", "tusd", "usde", "usdd", "pyusd", "busd", "usds", "usd1", "rlusd",
    "eurc", "gusd", "frax", "lusd", "susde", "usdp", "usdx", "ustc", "bfusd",
    "wbtc", "weth", "steth", "wsteth", "weeth", "cbbtc", "reth", "wbeth", "cbeth", "bsc-usd",
    "lbtc", "solvbtc", "meth", "ezeth", "rseth", "jitosol", "msol", "bnsol", "wbnb", "btcb", "paxg", "xaut",
}
BINANCE = ["https://data-api.binance.vision", "https://api.binance.com", "https://api1.binance.com"]
estado = {"inicio": datetime.now(timezone.utc).isoformat(), "fuentes": {}, "errores": []}


def get(url, intentos=3, espera=3):
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            if i == intentos - 1:
                raise
            time.sleep(espera * (i + 1))


def binance(path):
    ultimo = None
    for base in BINANCE:
        try:
            return get(base + path), base
        except Exception as e:  # noqa: BLE001
            ultimo = e
    raise ultimo


def guardar_csv(nombre, filas, campos):
    with open(os.path.join(OUT, nombre), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def main():
    os.makedirs(OUT, exist_ok=True)

    # 1. Universo por volumen
    mercados = get(
        "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc"
        "&per_page=120&page=1&price_change_percentage=7d,30d"
    )
    estado["fuentes"]["coingecko_markets"] = "ok"

    # 2. Pares USDT disponibles en Binance
    info, base_info = binance("/api/v3/exchangeInfo?permissions=SPOT")
    pares = {s["baseAsset"].upper() for s in info["symbols"] if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"}
    estado["fuentes"]["binance_exchangeinfo"] = base_info

    universo = []
    for m in mercados:
        sym = (m.get("symbol") or "").lower()
        if sym in EXCLUIR or m.get("id") in EXCLUIR:
            continue
        universo.append({
            "simbolo": sym.upper(),
            "coingecko_id": m["id"],
            "nombre": m["name"],
            "precio_usd": m.get("current_price"),
            "volumen_24h_usd": m.get("total_volume"),
            "capitalizacion_usd": m.get("market_cap"),
            "cambio_7d_pct": m.get("price_change_percentage_7d_in_currency"),
            "cambio_30d_pct": m.get("price_change_percentage_30d_in_currency"),
            "par_binance": f"{sym.upper()}USDT" if sym.upper() in pares else "",
        })
        if len(universo) == 60:
            break
    guardar_csv("universo.csv", universo, list(universo[0].keys()))

    # 3. Cierres diarios (solo velas cerradas) y precio actual
    cierres, verif = [], []
    hoy_ms = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    precios_bn = {}
    try:
        todos, _ = binance("/api/v3/ticker/price")
        precios_bn = {t["symbol"]: float(t["price"]) for t in todos}
        estado["fuentes"]["binance_ticker"] = "ok"
    except Exception as e:  # noqa: BLE001
        estado["errores"].append(f"ticker: {e}")

    for u in universo:
        par = u["par_binance"]
        if not par:
            continue
        try:
            velas, base = binance(f"/api/v3/klines?symbol={par}&interval=1d&limit=400")
            for v in velas:
                if v[0] >= hoy_ms:  # vela en curso
                    continue
                fecha = datetime.fromtimestamp(v[0] / 1000, timezone.utc).strftime("%Y-%m-%d")
                cierres.append({"fecha": fecha, "simbolo": u["simbolo"], "apertura": v[1], "maximo": v[2],
                                "minimo": v[3], "cierre": v[4], "volumen_usdt": v[7]})
        except Exception as e:  # noqa: BLE001
            estado["errores"].append(f"klines {par}: {e}")
        pb = precios_bn.get(par)
        pc = u["precio_usd"]
        verif.append({
            "simbolo": u["simbolo"],
            "precio_binance": pb if pb is not None else "",
            "precio_coingecko": pc if pc is not None else "",
            "diferencia_pct": round(abs(pb - pc) / pc * 100, 3) if pb and pc else "",
        })
        time.sleep(0.15)
    guardar_csv("cierres.csv", cierres, ["fecha", "simbolo", "apertura", "maximo", "minimo", "cierre", "volumen_usdt"])
    guardar_csv("verificacion.csv", verif, ["simbolo", "precio_binance", "precio_coingecko", "diferencia_pct"])
    if cierres:
        estado["ultimo_cierre"] = max(c["fecha"] for c in cierres)

    # 4. Global (dominancia)
    try:
        g = get("https://api.coingecko.com/api/v3/global")["data"]
        json.dump({
            "btc_dominancia_pct": g["market_cap_percentage"].get("btc"),
            "eth_dominancia_pct": g["market_cap_percentage"].get("eth"),
            "capitalizacion_total_usd": g["total_market_cap"].get("usd"),
            "actualizado": g.get("updated_at"),
        }, open(os.path.join(OUT, "global.json"), "w"), indent=2)
        estado["fuentes"]["coingecko_global"] = "ok"
    except Exception as e:  # noqa: BLE001
        estado["errores"].append(f"global: {e}")

    # 5. Funding (best effort; puede estar bloqueado por región)
    try:
        filas = []
        for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]:
            d = get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}", intentos=1)
            filas.append({"simbolo": sym, "funding_rate": d.get("lastFundingRate")})
        guardar_csv("funding.csv", filas, ["simbolo", "funding_rate"])
        estado["fuentes"]["binance_funding"] = "ok"
    except Exception as e:  # noqa: BLE001
        estado["errores"].append(f"funding: {e}")

    # 6. Dólar cripto
    try:
        d = get("https://criptoya.com/api/usdt/ars/1")
        json.dump(d, open(os.path.join(OUT, "dolar_cripto.json"), "w"), indent=2)
        estado["fuentes"]["criptoya"] = "ok"
    except Exception as e:  # noqa: BLE001
        estado["errores"].append(f"criptoya: {e}")

    estado["fin"] = datetime.now(timezone.utc).isoformat()
    estado["monedas_universo"] = len(universo)
    estado["monedas_con_cierres"] = len({c["simbolo"] for c in cierres})
    json.dump(estado, open(os.path.join(OUT, "estado.json"), "w"), indent=2)
    print(json.dumps(estado, indent=2))
    if not cierres:
        sys.exit("Sin cierres: revisar fuentes")


if __name__ == "__main__":
    main()
