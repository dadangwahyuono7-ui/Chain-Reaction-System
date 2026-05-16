import time
import MetaTrader5 as mt5
from engine.connection import connect_mt5
from engine.core import SacredDoctrineAnalyst
from engine.executor import SultanExecutor
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
    layout["header"].update(Panel(f"[bold gold1]🔱 SULTAN SNIPER ENGINE v2.0 - SACRED DOCTRINE 🔱[/bold gold1]", style="blue"))

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
    layout["account_panel"].update(Panel(acc_table, title="[bold]Account[/bold]", border_style="cyan"))

    # 3. Market Matrix (The Core)
    states = analyst.states
    matrix_table = Table(title=f"Market Matrix: {symbol}")
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
    sig_text = "[bold green]NO SIGNAL[/bold green]"
    if signal:
        sig_text = f"[bold blink yellow]🔥 {signal['reason']} 🔥[/bold blink yellow]"
        
    layout["footer"].update(Panel(f"Signal: {sig_text}", style="bold white"))

    return layout

def main():
    symbol = "XAUUSD"
    if not connect_mt5():
        return

    analyst = SacredDoctrineAnalyst(symbol)
    executor = SultanExecutor(symbol)

    console.print(f"[bold green]Scanning {symbol} for Sacred Doctrine setups...[/bold green]")

    with Live(create_dashboard(analyst, executor, symbol), refresh_per_second=1) as live:
        while True:
            try:
                # 1. Update Market Data
                analyst.update()
                
                # 2. Check for Signals
                signal = analyst.get_strike_signal()
                if signal:
                    # In a real scenario, you'd check settings for auto_trade
                    # For now, we just display it.
                    pass
                
                # 3. Refresh UI
                live.update(create_dashboard(analyst, executor, symbol))
                
                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                time.sleep(5)

if __name__ == "__main__":
    main()
