# CHAIN REACTION Execution Tasks

## Phase 1: Environment & Connectivity
- [ ] Initialize Python Environment (`python -m venv venv`)
- [ ] Install dependencies (`MetaTrader5`, `pandas`, `fastapi`, `uvicorn`)
- [ ] Establish MT5 Connection Bridge
- [ ] Implement Live Data Streamer (Fetch M5 to Daily candles)

## Phase 2: Core Logic (Sacred Doctrine)
- [ ] Implement `CMP_Scanner`: Identify Master DNA (H4/Daily)
- [ ] Implement `VR_Tracker`: Detect "Lekukan" (Tests) against Master
- [ ] Implement `CF_Validator`: Timing check (`child > parent`) & Confirmation Strike
- [ ] Implement `Barrier_Guard`: 35-pip VETO logic
- [ ] Implement `TP_Profiler`: Dynamic SNR targeting (M5 -> M15, etc.)

## Phase 3: Trade Execution & Management
- [ ] Implement `Order_Executor`: MT5 position opening with SL/TP
- [ ] Implement `BE_Protector`: 10-pip auto-breakeven
- [ ] Implement `TP_Paksa`: Exit on "Hang ke-2" or News < 30m
- [ ] Implement `DNA_Vault`: Logging failed patterns to `dna_vault.json`

## Phase 4: Web Dashboard (UI/UX)
- [ ] Initialize Next.js Dashboard
- [ ] Build Fractal Hierarchy Visualizer
- [ ] Implement Real-time Verdict Card
- [ ] Connect Backend API to MT5/Engine

## Phase 5: Testing & Refinement
- [ ] Backtest logic against 1 month of XAUUSD data
- [ ] Verify "Elephant/Tsunami" setup escalation
- [ ] User Acceptance Testing (Commander Dadang Review)
