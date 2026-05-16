# CHAIN REACTION System Implementation Plan

## Overview
The **CHAIN REACTION System** (Sultan Sniper Edition) is an elite automated trading analyst and execution engine built exclusively for Commander Dadang. It implements the "Sacred Doctrine" with a focus on institutional-grade precision, fractal inheritance, and strict barrier protection.

## Core Philosophy: The Sultan Sniper
- **Inheritance**: H4/Daily CMP sets the "Master DNA". All lower TFs inherit this bias.
- **Testing (VR)**: Counter-trend breakouts are "tests" (VR) of the parent TF.
- **The Strike (CF)**: Entry only occurs when a "Lekukan" (curve) confirms the return to Master direction.
- **Barrier Guard**: No entry if price is > 35 pips from the Master Barrier.

## System Architecture

```mermaid
graph TD
    subgraph "MetaTrader 5 (Data & Execution)"
        MT5[MT5 Terminal]
        MT5_Bridge[Python MT5 Library]
    end

    subgraph "Chain Reaction Engine (Logic)"
        Engine[Analysis Engine]
        CMP_Module[CMP Identifier]
        VR_Module[VR Hunt Logic]
        CF_Module[CF Validation]
        Time_Law[Chain Validation System]
        News_Filter[Fundamental & DXY Scan]
    end

    subgraph "Backend & Storage"
        API[FastAPI / Node.js]
        DB[(PostgreSQL/Redis)]
    end

    subgraph "Web Dashboard (UI/UX)"
        Web[Next.js Dashboard]
        Visuals[Fractal Cascade Visualizer]
    end

    MT5 <--> MT5_Bridge
    MT5_Bridge <--> Engine
    Engine --> API
    API <--> DB
    API <--> Web

## Detailed Execution Flow

```mermaid
flowchart TD
    Start([Start Cycle]) --> Data[Fetch Candles M5 to Daily]
    Data --> News{News Check}
    News -- "AVOID" --> Idle([Idle - Skip Setup])
    News -- "CLEAR/CAUTION" --> CMP[Identify Active CMP for all TFs]
    
    CMP --> Chain{Chain Validation}
    Chain -- "No Parent CMP" --> Idle
    Chain -- "CMP Active" --> VRHunt[Hunt for VR on Child TF]
    
    VRHunt -- "VR Detected" --> TimeLaw{Check Time Law}
    TimeLaw -- "Child Born After Parent" --> CFHunt[Hunt for CF Reversal]
    TimeLaw -- "Invalid Timing" --> Reset[Reset Child CMP]
    
    CFHunt -- "CF Confirmed" --> Strike{Strike Entry?}
    Strike -- "Yes" --> Execute[Execute MT5 Order]
    Strike -- "No" --> Wait[Wait for Next Candle]
    
    Execute --> Manage[Manage Trade: BE Protect / TP Hierarchy]
    Manage --> Exit([Exit Trade])
```
```

---

## Core Engine Logic (Sacred Doctrine Implementation)

### 1. MT5 Data Fetcher & Account Sync
- **Target**: Raw candle data and dynamic account metadata.
- **Universal Support**:
    - **Balance & Equity**: Auto-detect amount and currency (USD, USC/Cent, IDR).
    - **Server Detection**: Read broker server info for dynamic logging.
    - **Margin/Leverage**: Automatically adjust lot calculation based on account specifications.
- **Method**: Use `MetaTrader5` Python package (`mt5.account_info()`).
- **Hierarchy Sync**: Simultaneous data pull for Daily, H4, H1, M30, M15, M5.
- **Guardian Check**: Verify TF alignment (e.g., ensure M5 has 3 candles within M15).

### 2. The Logic Pipeline
1.  **Fundamental Filter**: Fetch DXY data and Economic Calendar.
2.  **Master DNA Sync**: Identify H4/Daily CMP. Broadcast bias to all child TFs.
3.  **VR Escalation Tracking**: 
    - M5 VR tests M15 Master.
    - M15 VR tests M30 Master.
    - M30 VR tests H1 Master.
    - H1 VR tests H4 Master.
4.  **CF Strike Validation**: Confirm return to Master direction with timing check (`child_time > parent_time`).
5.  **Barrier Guard Check**: Calculate distance from Master BO. VETO if > 35 pips.
6.  **TP Profiling**:
    - CF M5 -> Target SNR M15.
    - CF M15 -> Target SNR M30.
    - CF M30 -> Target SNR H1.
    - CF H1 -> Target SNR H4.

---

## Proposed Components

### [NEW] MT5 Integration Module (`engine/mt5_bridge.py`)
- Initializes connection to MT5.
- Functions to `get_candles(symbol, timeframe, count)`.
- Functions to `execute_order(type, volume, sl, tp)`.

### [NEW] Analysis Core (`engine/core.py`)
- Implements `calculate_cmp(candles)`.
- Implements `validate_chain(h4_data, m30_data, m5_data)`.
- Implements the **Fractal Cascade System** (Failure at M5 -> Escalation to M15, etc.).

### [NEW] Web Dashboard (`dashboard/`)
- A premium, dark-themed Next.js application.
- **Features**:
    - **Real-time Chain Status**: Visual tree showing parent-child validity.
    - **CMP Heatmap**: Current state of all timeframes.
    - **Signal Verdict Card**: Matching the "Chain Reaction Verdict" format.
    - **DXY & News Widget**: Live fundamental risk levels.

---

## UI/UX Wireframe (ASCII)

```text
+--------------------------------------------------------------------------+
|  CHAIN REACTION v1.0 | COMMANDER DADANG EXCLUSIVE | [ LIVE ] [ DXY: 104.2 ] |
+--------------------------------------------------------------------------+
|  [ MARKET BIAS ]   |  [ FUNDAMENTALS ]       |  [ NEWS ALERT ]           |
|  GOLD: BEARISH     |  DXY: STRENGTHENING     |  CPI in 2h 15m (AVOID)    |
+--------------------------------------------------------------------------+
|                                                                          |
|  FRACTAL CASCADE STATUS                                                  |
|  DAILY: [BUY]  H4: [BUY]  H1: [SELL]  M30: [SELL]  M15: [VR]  M5: [CF...]  |
|                                                                          |
+--------------------------------------------------------------------------+
|  [ MAIN ANALYSIS VIEW ]                     |  [ ACTIVE CHAIN ]          |
|                                             |                            |
|  DIRECTION: SELL                            |  H4 CMP (T0)   [OK]        |
|  CONFIDENCE: HIGH                           |    |                       |
|  ENTRY: 2345.12                             |    +-- M30 VR  [OK]        |
|  TP 1: 2338.50                              |    |   (T1 > T0)           |
|  TP 2: 2330.00                              |    |                       |
|  SL:   2352.00                              |    +-- M5 CF   [WAIT]      |
|                                             |                            |
+--------------------------------------------------------------------------+
|  [ LOGS / HISTORY ]                                                      |
|  12:55 - M5 VR Detected for M30 Parent...                                |
|  12:50 - H4 CMP Reset after VR appearance...                             |
+--------------------------------------------------------------------------+
```

---

## Verification Plan

### Automated Testing
- **Backtesting Module**: Run Sacred Doctrine logic against historical MT5 data to verify CMP/VR/CF accuracy.
- **Time Law Validation**: Unit tests to ensure no child signal is ever accepted if it precedes the parent.

### Manual Verification
1.  Compare Engine analysis with Commander Dadang's manual chart reading.
2.  Verify MT5 execution speed and SL/TP placement.
3.  Check Dashboard responsiveness and real-time data sync.

## User Review Required

> [!IMPORTANT]
> **MT5 Connection**: To run the engine, MT5 must be installed on the same Windows machine. I will need the account credentials or for you to be logged in to the terminal.

> [!WARNING]
> **TP Hierarchy**: The system will strictly enforce "Never eat another TF's portion." Manual intervention to extend TP might break the mathematical balance of the doctrine.

> [!CAUTION]
> **Fundamental Skip**: During NFP or Fed Rate decisions, the engine will automatically enter "AVOID" mode and skip all setups.
