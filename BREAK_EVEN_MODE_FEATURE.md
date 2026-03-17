# Break-Even Mode Feature

## Overview
Added radio button selection in Settings to choose between two break-even modes:
- **Copy Master**: Closes positions when a close signal is received from the master trader
- **Custom**: Ignores close signals and uses custom break-even settings instead

## Changes Made

### 1. Configuration (`src/config.py`)
- Added new field: `break_even_mode: str = "copy_master"`
- Updated `load_config()` to read `BREAK_EVEN_MODE` from environment

### 2. Settings UI (`src/gui/settings.py`)
- Added new method `_add_radio_row()` to create radio button groups
- Updated Break-Even Settings card to include:
  - "Enabled" checkbox (existing)
  - **"Mode" radio buttons** (NEW):
    - Copy Master (default)
    - Custom
  - "Activate At (pips)" field (existing)
  - "Offset (pips)" field (existing)
- Updated `_auto_save()` to save `BREAK_EVEN_MODE` to .env file

### 3. Discord Bot (`src/discord_bot.py`)
- Updated close order handling to check `break_even_mode`:
  - If `copy_master`: Process close orders normally (close the position)
  - If `custom`: Ignore close orders and log that custom settings are being used

### 4. Environment Files
- Updated `.env` with `BREAK_EVEN_MODE=copy_master`
- Updated `deploy/create_release_exe.py` template with the new setting

## How It Works

### Copy Master Mode (Default)
When a close signal is received from the master trader:
1. Bot detects the close order signal
2. Finds the corresponding position
3. Closes the position immediately
4. Logs: "Break-Even Mode: COPY MASTER - Processing close order"

### Custom Mode
When a close signal is received from the master trader:
1. Bot detects the close order signal
2. Ignores the close signal
3. Logs: "Break-Even Mode: CUSTOM - Ignoring close order, using custom settings"
4. Position remains open and is managed by custom break-even settings:
   - Moves stop loss to break-even when profit reaches "Activate At" pips
   - Uses "Offset" pips as the break-even stop loss offset

## Settings UI
The Break-Even Settings card now displays:
```
Break-Even Settings
├─ Enabled [✓]
├─ Mode: ○ Copy Master  ○ Custom
├─ Activate At (pips): [300.0]
└─ Offset (pips): [100.0]
```

## Environment Variable
```env
BREAK_EVEN_MODE=copy_master  # or "custom"
```

## Default Behavior
- Default mode: `copy_master` (maintains backward compatibility)
- Users can switch to `custom` mode in Settings UI
- Changes are auto-saved to .env file
