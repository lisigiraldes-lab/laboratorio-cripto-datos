# Laboratorio cripto: datos

Precios diarios públicos que usa el Laboratorio cripto, un portafolio en papel (sin dinero real).

Una GitHub Action corre todos los días a las 06:17 de Buenos Aires y deja en `data/latest/`:

| Archivo | Contenido |
|---|---|
| `universo.csv` | Top 60 criptomonedas por volumen (CoinGecko), sin stablecoins ni tokens envueltos |
| `cierres.csv` | Cierres diarios de los últimos 400 días de cada moneda con par USDT en Binance |
| `verificacion.csv` | Precio actual en Binance y CoinGecko y su diferencia porcentual |
| `global.json` | Dominancia de BTC y capitalización total |
| `funding.csv` | Funding de perpetuos de Binance, si está disponible |
| `dolar_cripto.json` | Cotización USDT/ARS por exchange (CriptoYa) |
| `estado.json` | Qué fuentes respondieron y qué falló |

Solo usa endpoints públicos, sin claves ni credenciales. Para correrla a mano: pestaña **Actions** → **Datos diarios** → **Run workflow**.
