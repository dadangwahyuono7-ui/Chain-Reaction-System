# CHAIN REACTION Dashboard UI/UX Design

## Design Aesthetic
- **Theme**: Obsidian Night (Deep blacks, slate grays, vibrant neon accents for signals).
- **Typography**: Inter / JetBrains Mono (for the "Technical/Elite" feel).
- **Colors**:
    - `Bullish/BUY`: #00ff88 (Electric Emerald)
    - `Bearish/SELL`: #ff3366 (Neon Crimson)
    - `Neutral/Wait`: #718096 (Cool Gray)
    - `Background`: #0a0a0c

## Wireframe Components

### 1. Global Header
- Title: `CHAIN REACTION v1.0`
- User: `Commander Dadang (Premium Account)`
- Connection Status: `MT5: CONNECTED`
- Market Time: `GMT+X`

### 2. Market Pulse (Top Bar)
- XAUUSD Price (Live)
- DXY Index (Live + Trend Arrow)
- Volatility Index
- News Countdown (Next High Impact)

### 3. Fractal Chain Visualization (The Core)
A horizontal tree view showing the hierarchy:
`Daily` → `H4` → `H1` → `M30` → `M15` → `M5`
Each node shows:
- CMP State (Buy/Sell)
- Confirmation Time
- Validity (Green check/Red X)

### 4. The Verdict (Main Card)
A high-contrast card showing:
- **Action**: `STRONG SELL`
- **Confirmation**: `M5 CF VALID`
- **TP1/TP2/SL** in large, clear fonts.
- **Rationale**: Short, doctrine-based text.

---

## Mockup (Conceptual Layout)

```text
+--------------------------------------------------------------------------+
| [CR Logo] CHAIN REACTION | [MT5 OK] | [12:59:01] | CMD DADANG [Logout]   |
+--------------------------------------------------------------------------+
| XAUUSD: 2345.10 | DXY: 104.5 (+0.1%) | VOL: HIGH | NEXT NEWS: CPI (2h)   |
+--------------------------------------------------------------------------+
|                                                                          |
|  [ FRACTAL HIERARCHY ]                                                   |
|  +-------+     +-------+     +-------+     +-------+     +-------+       |
|  | DAILY |     |  H4   |     |  H1   |     |  M30  |     |  M5   |       |
|  |  BUY  |---->|  BUY  |---->|  SELL |---->|  VR   |---->|  CF   |       |
|  +-------+     +-------+     +-------+     +-------+     +-------+       |
|                                                                          |
+--------------------------------------------------------------------------+
|                                     |                                    |
| [ ANALYSIS VERDICT ]                | [ ACTIVE TRADE / SIGNAL ]          |
|                                     |                                    |
| DIRECTION : SELL                    | STATUS  : ENTRY PENDING            |
| CF TF     : M5                      | TRIGGER : 2344.50 (Minor SNR)      |
| GUARDIAN  : M15                     | SL      : 2355.00                  |
|                                     | TP 1    : 2335.00 (VR Area)        |
| RATIONALE:                          | TP 2    : 2320.00 (Barrier)        |
| H4 CMP confirmed. M30 VR valid.     |                                    |
| M5 CF breakout detected.            | [ EXECUTE MT5 ] [ CANCEL ]         |
|                                     |                                    |
+--------------------------------------------------------------------------+
| [ LOGS ]                                                                 |
| 12:58:10 - M5 Candle Closed at 2344.20. CF Status: VALID.                |
| 12:55:00 - M30 VR confirmed at 2348.00. Chain timing: VALID.             |
+--------------------------------------------------------------------------+
```
