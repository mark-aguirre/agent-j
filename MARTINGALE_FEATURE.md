# Martingale Lot Sizing Feature

## Overview
The martingale lot sizing feature automatically doubles the lot size after a losing trade and resets to the base lot size after a winning trade. This is a risk management strategy that aims to recover losses with the next winning trade.

## How It Works

### Example Scenario:
- **Base lot size**: 0.01
- **Multiplier**: 2.0 (doubles the lot)
- **Max consecutive losses**: 3

**Trade Sequence:**
1. **Trade 1**: Lot size 0.01 → **Loss** (-$10)
2. **Trade 2**: Lot size 0.02 → **Loss** (-$20)  
3. **Trade 3**: Lot size 0.04 → **Profit** (+$40)
4. **Trade 4**: Lot size 0.01 (reset to base)

### Safety Features:
- **Maximum consecutive losses limit**: Prevents unlimited lot size growth
- **Respects min/max lot limits**: Won't exceed your broker's limits
- **Emergency reset**: Automatically resets after reaching max losses
- **Persistent state**: Remembers state between bot restarts

## Configuration

### Method 1: GUI Settings (Recommended)
1. **Open the bot GUI**
2. **Go to Settings tab**
3. **Find "Martingale Lot Sizing" section**
4. **Configure the settings:**
   - ✅ **Enabled**: Check to enable martingale
   - **Base Lot Size**: Starting lot size (e.g., 0.01)
   - **Multiplier**: Multiplier after loss (e.g., 2.0 = double)
   - **Max Consecutive Losses**: Max losses before reset (e.g., 3)
5. **Settings auto-save** when you change them

### Method 2: Environment File
Add these settings to your `.env` file:

```env
# Martingale Settings
USE_MARTINGALE=true
MARTINGALE_BASE_LOT=0.01
MARTINGALE_MULTIPLIER=2.0
MARTINGALE_MAX_LOSSES=3
```

### Configuration Options:

- **USE_MARTINGALE**: Enable/disable martingale (true/false)
- **MARTINGALE_BASE_LOT**: Starting lot size (e.g., 0.01)
- **MARTINGALE_MULTIPLIER**: Multiplier after loss (e.g., 2.0 = double)
- **MARTINGALE_MAX_LOSSES**: Max consecutive losses before reset (e.g., 3)

## Important Notes

### ⚠️ Risk Warning
Martingale strategies can lead to significant losses if you experience a long losing streak. Use with caution and proper risk management.

### When Martingale is Active:
- **Overrides other lot sizing**: When enabled, martingale takes priority over fixed lot, risk percent, and fixed money modes
- **Uses base lot**: The `MARTINGALE_BASE_LOT` setting becomes your primary lot size
- **Automatic tracking**: The bot automatically tracks trade results and adjusts lot sizes

### State Persistence:
- Martingale state is saved to `martingale_state.json`
- State persists between bot restarts
- Manual reset: Delete the file to reset martingale state

## Monitoring

### Dashboard Display
The bot shows martingale status in the GUI dashboard:
- **Next Lot**: Shows the lot size for the next trade
- **Configuration**: Shows martingale settings in the config section
- **Color coding**: 
  - 🟢 Green: Normal state (no recent losses)
  - 🔴 Red: After losses (shows "L2" for 2 consecutive losses)

### Log Messages
The bot logs martingale activity:

```
[INFO] Martingale: Loss trade, multiplier increased to 2.0
[INFO] Using martingale lot size: 0.02
[INFO] Martingale: Profit trade, reset to base lot (multiplier: 1.0)
```

## Compatibility

- ✅ Works with all order types (BUY, SELL, LIMIT, STOP)
- ✅ Compatible with break-even and trailing stop features
- ✅ Respects daily limits and max trades settings
- ✅ Works in both MASTER and CLIENT modes

## Example Usage

1. **Enable martingale** via GUI Settings or `.env`:
   - GUI: Settings → Martingale Lot Sizing → ✅ Enabled
   - .env: `USE_MARTINGALE=true`

2. **Configure parameters**:
   - Base Lot: 0.01
   - Multiplier: 2.0  
   - Max Losses: 3

3. **Start the bot** - you'll see:
   ```
   Martingale: Enabled (Base Lot: 0.01, Multiplier: 2.0x, Max Losses: 3)
   ```

4. **Monitor in dashboard**: Next Lot shows current lot size and loss count

5. **Trade results** are automatically tracked and lot sizes adjusted accordingly.

## Troubleshooting

### Reset Martingale State
If you need to reset the martingale state:
```bash
# Delete the state file
rm martingale_state.json
```

### Check Current State
The current martingale state is logged on startup and after each trade.

### Disable Martingale
Set `USE_MARTINGALE=false` in your `.env` file to disable the feature.