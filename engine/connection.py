import MetaTrader5 as mt5
import pandas as pd
import os
import time
from rich.console import Console
from rich.table import Table

console = Console()

def connect_mt5():
    """Connects to MetaTrader 5 and returns True if successful."""
    # Attempt to initialize without path first
    if not mt5.initialize():
        console.print("[bold yellow]MT5 Terminal not detected. Attempting Auto-Ignition...[/bold yellow]")
        
        # Common MT5 paths for IC Markets or standard installations
        mt5_paths = [
            "C:/Program Files/IC Markets MetaTrader 5/terminal64.exe",
            "C:/Program Files/MetaTrader 5/terminal64.exe",
        ]
        
        success = False
        for path in mt5_paths:
            if os.path.exists(path):
                console.print(f"[cyan]Launching MT5 from: {path}[/cyan]")
                if mt5.initialize(path=path):
                    success = True
                    # Give it some time to fully load
                    time.sleep(5)
                    break
        
        if not success:
            console.print("[bold red]CRITICAL: MT5 Terminal not found. Please open MT5 manually.[/bold red]")
            return False
            
    # Success check
    account_info = mt5.account_info()
    if account_info is None:
        console.print("[bold red]MT5 Connected but Account Info missing. Please login to MT5.[/bold red]")
        return False
        
    # Display Account Info
    table = Table(title="CHAIN REACTION - Account Sync")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Account ID", str(account_info.login))
    table.add_row("Server", account_info.server)
    table.add_row("Currency", account_info.currency)
    table.add_row("Balance", f"{account_info.balance:,.2f}")
    table.add_row("Equity", f"{account_info.equity:,.2f}")
    
    console.print(table)
    return True

if __name__ == "__main__":
    connect_mt5()
    mt5.shutdown()
