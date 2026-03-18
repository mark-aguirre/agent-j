#!/usr/bin/env python3
"""
Fetch MT5 trade history and analyze martingale state
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import json
import sys

def connect_mt5():
    """Connect to MT5"""
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return False
    print("✓ Connected to MT5")
    return True

def get_trade_history(days=7):
    """Get trade history from the last N days"""
    try:
        # Get trades from the last N days
        from_date = datetime.now() - timedelta(days=days)
        deals = mt5.history_deals_get(from_date, datetime.now())
        
        if deals is None:
            print(f"Failed to get deals: {mt5.last_error()}")
            return []
        
        print(f"\n✓ Retrieved {len(deals)} deals from the last {days} days")
        return deals
    except Exception as e:
        print(f"Error getting trade history: {e}")
        return []

def analyze_trades(deals):
    """Analyze trades for martingale patterns"""
    if not deals:
        print("No trades found")
        return
    
    # Convert to DataFrame for easier analysis
    df_deals = pd.DataFrame(list(deals))
    
    # Filter for closed positions (DEAL_TYPE_SELL or DEAL_TYPE_BUY that are closed)
    print("\n" + "="*80)
    print("TRADE HISTORY ANALYSIS")
    print("="*80)
    
    # Group by position ticket to see profit/loss
    trades = []
    for deal in deals:
        trades.append({
            'ticket': deal.ticket,
            'position_id': deal.position_id,
            'symbol': deal.symbol,
            'type': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL',
            'volume': deal.volume,
            'price': deal.price,
            'profit': deal.profit,
            'commission': deal.commission,
            'time': datetime.fromtimestamp(deal.time),
            'entry_time': deal.entry,
        })
    
    # Sort by time
    trades.sort(key=lambda x: x['time'])
    
    print(f"\nTotal Deals: {len(trades)}")
    print("\nRecent Trades (Last 20):")
    print("-" * 80)
    print(f"{'Ticket':<12} {'Symbol':<8} {'Type':<6} {'Volume':<8} {'Profit':<10} {'Time':<20}")
    print("-" * 80)
    
    for trade in trades[-20:]:
        profit_str = f"${trade['profit']:.2f}"
        if trade['profit'] < 0:
            profit_str = f"-${abs(trade['profit']):.2f}"
        print(f"{trade['ticket']:<12} {trade['symbol']:<8} {trade['type']:<6} {trade['volume']:<8} {profit_str:<10} {trade['time'].strftime('%Y-%m-%d %H:%M:%S'):<20}")
    
    # Analyze consecutive losses
    print("\n" + "="*80)
    print("MARTINGALE ANALYSIS")
    print("="*80)
    
    # Get closed positions
    positions = mt5.positions_get()
    print(f"\nOpen Positions: {len(positions) if positions else 0}")
    
    # Analyze profit/loss sequence
    closed_trades = [t for t in trades if t['profit'] != 0]
    
    if closed_trades:
        print(f"\nClosed Trades Analysis (Last 10):")
        print("-" * 80)
        consecutive_losses = 0
        for i, trade in enumerate(closed_trades[-10:]):
            result = "LOSS" if trade['profit'] < 0 else "PROFIT"
            if trade['profit'] < 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0
            
            print(f"{i+1}. {trade['symbol']:<8} {trade['type']:<6} Vol: {trade['volume']:<6} Profit: ${trade['profit']:>8.2f} [{result}] (Consecutive Losses: {consecutive_losses})")
    
    # Summary stats
    total_profit = sum(t['profit'] for t in trades)
    winning_trades = len([t for t in trades if t['profit'] > 0])
    losing_trades = len([t for t in trades if t['profit'] < 0])
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total Profit/Loss: ${total_profit:.2f}")
    print(f"Winning Trades: {winning_trades}")
    print(f"Losing Trades: {losing_trades}")
    if winning_trades + losing_trades > 0:
        win_rate = (winning_trades / (winning_trades + losing_trades)) * 100
        print(f"Win Rate: {win_rate:.1f}%")
    
    # Check martingale state file
    print("\n" + "="*80)
    print("CURRENT MARTINGALE STATE")
    print("="*80)
    try:
        with open('martingale_state.json', 'r') as f:
            state = json.load(f)
            print(json.dumps(state, indent=2))
    except FileNotFoundError:
        print("No martingale_state.json found")
    
    return trades

def main():
    if not connect_mt5():
        sys.exit(1)
    
    try:
        deals = get_trade_history(days=7)
        analyze_trades(deals)
    finally:
        mt5.shutdown()
        print("\n✓ Disconnected from MT5")

if __name__ == "__main__":
    main()
