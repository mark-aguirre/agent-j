# Settings UI Update - Loss Recovery

## New Settings Card Added

A new "Loss Recovery Settings" card has been added to the Settings tab in the GUI.

### Location
- Left column, after "Daily Goal Settings"

### Fields

1. **Enabled** (Checkbox)
   - Toggles loss recovery on/off
   - Default: `true`

2. **Recovery Target (pips)** (Text Input)
   - The pip target at which losses should be recovered
   - Default: `100.0`
   - This is the number of pips where the increased lot size will recover previous losses

3. **Info Label**
   - Displays: "💡 Automatically increases lot size to recover losses at the recovery target"
   - Helps users understand what the feature does

### Auto-Save
- All changes are automatically saved to `.env` file
- Live config is updated immediately without restart
- Settings persist across application restarts

### Environment Variables
```env
USE_LOSS_RECOVERY=true
RECOVERY_PIPS=100.0
```

## How Users Will Use It

1. Open the bot GUI
2. Go to Settings tab
3. Scroll to "Loss Recovery Settings" card
4. Toggle "Enabled" checkbox to turn on/off
5. Adjust "Breakeven Target (pips)" as needed
6. Settings save automatically

## Visual Layout

```
┌─────────────────────────────────────┐
│  Loss Recovery Settings             │
├─────────────────────────────────────┤
│  Enabled                         ☑  │
│  Recovery Target (pips)     [100.0] │
│                                     │
│  💡 Automatically increases lot     │
│     size to recover losses at the   │
│     recovery target                 │
└─────────────────────────────────────┘
```
