#!/usr/bin/env python3
"""
Debug martingale state tracking
"""
import MetaTrader5 as mt5
from datetime import datetime
import json

def debug_martingale():
    """Debug martingale state"""
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return
    
    print("="*80)
    print("MARTINGALE DEBUG")
    print("="*80)
    
    # Get today's deals
    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    to_date = datetime.now()
    
    deals = mt5.history_deals_get(from_date, to_date)
    
    if not deals:
        print("No deals found today")
        mt5.shutdown()
        return
    
    print(f"\nTotal deals today: {len(deals)}")
    
    # Filter for close deals (DEAL_ENTRY_OUT)
    close_deals = []
    for deal in deals:
        if (deal.type == mt5.DEAL_TYPE_SELL or deal.type == mt5.DEAL_TYPE_BUY) and \
           deal.entry == mt5.DEAL_ENTRY_OUT:
            close_deals.append(deal)
    
    print(f"Close deals (DEAL_ENTRY_OUT): {len(close_deals)}")
    
    # Sort by time
    close_deals.sort(key=lambda d: d.time)
    
    # Simulate martingale state tracking
    martingale_state = {
        'consecutive_losses': 0,
        'current_lot_multiplier': 1.0,
        'last_trade_result': None,
        'last_trade_ticket': None
    }
    
    print("\n" + "="*80)
    print("SIMULATING MARTINGALE STATE UPDATES")
    print("="*80)
    
    for i, deal in enumerate(close_deals):
        print(f"\n{i+1}. Deal {deal.ticket} | Position {deal.position_id}")
        print(f"   Type: {'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL'}")
        print(f"   Entry: {deal.entry} (OUT={mt5.DEAL_ENTRY_OUT})")
        print(f"   Profit: ${deal.profit:.2f}")
        print(f"   Magic: {deal.magic}")
        
        # Update state
        if deal.profit > 0:
            print(f"   → PROFIT: Reset to base lot")
            martingale_state['consecutive_losses'] = 0
            martingale_state['current_lot_multiplier'] = 1.0
            martingale_state['last_trade_result'] = 'profit'
        else:
            print(f"   → LOSS: Increase multiplier")
            martingale_state['consecutive_losses'] += 1
            martingale_state['current_lot_multiplier'] *= 2.0
            martingale_state['last_trade_result'] = 'loss'
        
        martingale_state['last_trade_ticket'] = deal.position_id
        
        print(f"   State: Losses={martingale_state['consecutive_losses']}, "
              f"Multiplier={martingale_state['current_lot_multiplier']}")
    
    print("\n" + "="*80)
    print("FINAL MARTINGALE STATE")
    print("="*80)
    print(json.dumps(martingale_state, indent=2))
    
    # Check current state file
    print("\n" + "="*80)
    print("CURRENT STATE FILE")
    print("="*80)
    try:
        with open('martingale_state.json', 'r') as f:
            current = json.load(f)
            print(json.dumps(current, indent=2))
    except FileNotFoundError:
        print("No martingale_state.json found")
    
    mt5.shutdown()

if __name__ == "__main__":
    debug_martingale()
