# Chain Reaction System

XAUUSD trading engine — MT5 EA + Bookmap order-flow bridge + Sultan Sniper Engine dashboard. Built by Commander Dadang Wahyuono.

## Setting up on a new PC

Needed on the machine first, installed manually (these are licensed/account-bound apps — no script can do this part):

- **MetaTrader 5**, logged into your broker account.
- **Bookmap**, connected to Rithmic (or your data feed).
- **Python 3.x** (check "Add to PATH" during install) — [python.org](https://python.org).
- *(optional, for remote access)* **cloudflared** — `winget install cloudflare.cloudflared`.

Then:

```powershell
git clone <this-repo-url>
cd <repo-folder>
.\setup.ps1
```

`setup.ps1` creates the Python venv and installs dependencies. It prints exactly what's still manual — MT5 EA attach, Bookmap addon load, and (if you want the `trade.dadangchatai.com` remote link) copying your `.cloudflared\` folder over from wherever it was configured before.

## Running a session

```powershell
bookmap-bridge\start_trading.ps1
```

Starts the Bookmap↔MT5 bridge, opens the Sultan Sniper Engine dashboard (maximized), and starts the Cloudflare tunnel if it's configured. Stop everything with `bookmap-bridge\stop_trading.ps1`.

## Layout

```
DD_ChainReaction_MultiTF_EA_v2.mq5   # production EA - compile in MetaEditor, attach to XAUUSD M5
DD_CMP_Indicator.mq5                 # CMP indicator the EA depends on
chain_settings.json                  # runtime config (lot size, risk %, magic number, ...)
setup.ps1                            # one-time: venv + dependencies
bookmap-bridge/
  bookmap_addon.py                   # loads INSIDE Bookmap's own Code Editor
  udp_listener.py                    # the core engine process (your venv)
  sultan_dashboard_server.py         # the dashboard window + local web server
  sultan/                            # dashboard HTML/CSS/JS
  start_trading.ps1 / stop_trading.ps1
```

See `CLAUDE.md` for the full doctrine (CMP/VR/CF), architecture notes, and change history.
