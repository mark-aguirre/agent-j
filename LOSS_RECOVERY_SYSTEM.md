# Loss Recovery System

## Overview
Automatically recovers previous losses by increasing lot size on new trades. When a trade reaches the breakeven point (100 pips by default), the losses are recovered.

## How It Works

1. **Loss Tracking**: Every closed trade's profit/loss is tracked in `_internal/loss_recovery.json`
   - Losses are added to cumulative loss
   - Profits reduce cumulative loss

2. **Recovery Calculation**: When opening a new trade:
   - System calculates additional lot size needed to recover losses at breakeven pips
   - Formula: `recovery_lots = cumulative_loss / (breakeven_pips × pip_value)`
   - Rounds up to 0.01 lots (2 decimals)

3. **Automatic Recovery**: 
   - Base lot size + recovery lots = total lot size
   - When trade hits 100 pips profit, losses are recovered
   - System resets cumulative loss once recovered

## Example

**Current Status:**
- Cumulative loss: $15.10
- Breakeven setting: 100 pips
- Base lot size: 0.01

**Next Trade:**
- Recovery lots needed: $15.10 / (100 pips × $10) = 0.015 → rounds to 0.02
- Total lot size: 0.01 + 0.02 = 0.03 lots

**At 100 pips profit:**
- Profit = 0.03 × 100 × $10 = $30
- Net after recovery: $30 - $15.10 = $14.90 profit
- Cumulative loss reset to $0

## Configuration

Add to your `.env` file:

```env
# Loss Recovery Settings
USE_LOSS_RECOVERY=true
RECOVERY_PIPS=100.0
```

## Files Modified

- `src/config.py`: Added recovery settings
- `src/mt5_trader.py`: Added recovery logic and loss tracking
- `main.py`: Added closed position tracking to main loop
- `_internal/loss_recovery.json`: Stores cumulative loss data

## Manual Reset

To manually reset cumulative loss, edit `_internal/loss_recovery.json`:

```json
{
  "cumulative_loss": 0.0,
  "last_updated": "2026-03-10T00:00:00"
}
```
