import MetaTrader5 as mt5
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()

def connect_mt5():
    if not mt5.initialize():
        console.print("[bold red]Failed to initialize MT5[/bold red]")
        return False
    
    account_info = mt5.account_info()
    if account_info is None:
        console.print("[bold red]Failed to get account info. Make sure you are logged in.[/bold red]")
        return False
    
    # Display Account Info (Universal)
    table = Table(title="Sultan Sniper - Account Sync")
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
