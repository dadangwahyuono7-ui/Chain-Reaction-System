import time
import MetaTrader5 as mt5
from engine.connection import connect_mt5
from engine.core import SacredDoctrineAnalyst
from engine.executor import ChainReactionExecutor
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from datetime import datetime

console = Console()

def create_dashboard(analyst, executor, symbol):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    layout["body"].split_row(
        Layout(name="account_panel", ratio=1),
        Layout(name="market_panel", ratio=2)
    )

    # 1. Header
    layout["header"].update(Panel(f"[bold gold1]⛓️ CHAIN REACTION PROTOCOL v2.0 - SACRED DOCTRINE ⛓️[/bold gold1]", style="blue"))

    # 2. Account Panel
    acc = mt5.account_info()
    acc_table = Table(box=None)
    acc_table.add_column("Key", style="cyan")
    acc_table.add_column("Value", style="magenta")
    if acc:
        acc_table.add_row("Login", str(acc.login))
        acc_table.add_row("Balance", f"{acc.balance:,.2f} {acc.currency}")
        acc_table.add_row("Equity", f"{acc.equity:,.2f}")
        acc_table.add_row("Profit", f"{acc.profit:+.2f}")
    layout["account_panel"].update(Panel(acc_table, title="[bold]Chain Sync[/bold]", border_style="cyan"))

    # 3. Market Matrix (The Core)
    states = analyst.states
    matrix_table = Table(title=f"Reaction Matrix: {symbol}")
    matrix_table.add_column("TF", justify="center")
    matrix_table.add_column("CMP", justify="center")
    matrix_table.add_column("Status", justify="center")
    matrix_table.add_column("Minor SNR", justify="center")
    matrix_table.add_column("Time", justify="center")

    for tf in ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]:
        st = states[tf]
        cmp_style = "bold green" if st.cmp == "BUY" else "bold red" if st.cmp == "SELL" else "white"
        status_style = "bold yellow" if st.status == "CF" else "bold blue" if st.status == "VR" else "white"
        
        # Format time
        time_str = datetime.fromtimestamp(st.cmp_change_time).strftime("%H:%M:%S") if st.cmp_change_time > 0 else "---"
        
        matrix_table.add_row(
            tf,
            f"[{cmp_style}]{st.cmp}[/{cmp_style}]",
            f"[{status_style}]{st.status}[/{status_style}]",
            f"S:{st.sup:.2f} R:{st.res:.2f}",
            time_str
        )

    layout["market_panel"].update(Panel(matrix_table, title="[bold]Sacred Hierarchy[/bold]", border_style="magenta"))

    # 4. Footer (Signal & Barrier)
    signal = analyst.get_strike_signal()
    
    # Barrier Status Calculation
    price = mt5.symbol_info_tick(symbol).bid if mt5.symbol_info_tick(symbol) else 0
    master = analyst.states["H4"] if analyst.states["H4"].cmp != "WAIT" else analyst.states["D1"]
    barrier_price = master.sup if master.cmp == "BUY" else master.res
    barrier_dist = abs(price - barrier_price) if barrier_price > 0 else 0
    
    barrier_style = "green" if barrier_dist <= 3.5 else "bold red"
    barrier_text = f"Barrier Guard: [ {barrier_dist:.2f} / 3.50 ]" if barrier_price > 0 else "Barrier Guard: [ SCANNING ]"
    
    sig_text = "[bold green]NO REACTION[/bold green]"
    if signal:
        sig_text = f"[bold blink yellow]⚡ {signal['reason']} ⚡[/bold blink yellow]"
        # Show SNR Hunter TP target if signal exists
        tp = executor.calculate_snr_hunter_tp(signal['action'], analyst, tf_name=signal['tf'])
        sig_text += f" | [cyan]Target TP: {tp:.2f}[/cyan]"
        
    layout["footer"].update(Panel(f"{barrier_text}  |  Signal: {sig_text}", style="bold white"))

    return layout

import json
import os

def load_settings():
    path = "chain_settings.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"auto_trade": False, "lot_size": 0.01, "max_layers": 3, "barrier_limit": 3.5}

def main():
    symbol = "XAUUSD"
    if not connect_mt5():
        return

    settings = load_settings()
    analyst = SacredDoctrineAnalyst(symbol)
    executor = ChainReactionExecutor(symbol, magic_number=settings.get("magic_number", 2026))
    executor.barrier_limit = settings.get("barrier_limit", 3.5)

    console.print(f"[bold green]Scanning {symbol} for Sacred Doctrine setups...[/bold green]")
    if settings.get("auto_trade"):
        console.print("[bold blink red]CHAIN REACTION ACTIVE! EXECUTION ARMED![/bold blink red]")

    last_strike_time = 0
    cooldown = 300 # 5 minutes between strikes per direction

    with Live(create_dashboard(analyst, executor, symbol), refresh_per_second=1) as live:
        while True:
            try:
                # 1. Update Market Data
                analyst.update()
                settings = load_settings() # Reload settings on the fly
                
                # 2. Check for Signals
                signal = analyst.get_strike_signal()
                if signal and settings.get("auto_trade"):
                    # Check Cooldown
                    if time.time() - last_strike_time > cooldown:
                        # CHECK MAX LAYERS
                        positions = mt5.positions_get(symbol=symbol, magic=settings.get("magic_number", 2026))
                        if len(positions) < settings.get("max_layers", 3):
                            # EXECUTE!
                            lot = settings.get("lot_size", 0.01)
                            success, msg = executor.execute_strike(
                                signal['action'], 
                                analyst, 
                                lot=lot, 
                                comment=f"Chain_{signal['tf']}_{signal.get('risk', 'REG')}"
                            )
                            if success:
                                last_strike_time = time.time()
                                console.print(f"[bold green]🚀 {msg}[/bold green]")
                            else:
                                console.print(f"[bold red]❌ {msg}[/bold red]")
                
                # 3. Refresh UI
                live.update(create_dashboard(analyst, executor, symbol))
                
                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                # console.print(f"[red]Error: {e}[/red]")
                time.sleep(5)

if __name__ == "__main__":
    main()
