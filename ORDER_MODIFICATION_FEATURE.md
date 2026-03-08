# Order Modification Feature

## Overview
The bot now supports detecting and synchronizing order modifications between Master and Client accounts.

## How It Works

### Master Mode
When running in master mode, the bot monitors all MT5 orders and detects:
- Entry price changes (pending orders)
- Stop Loss (SL) modifications
- Take Profit (TP) modifications
- Volume changes (partial closes)

When a change is detected, it sends a notification to Discord with:
- Ticket number
- Current order details
- List of changes made

### Client Mode
When running in client mode, the bot:
- Listens for modification messages from Discord
- Parses the modification details
- Applies the same changes to the corresponding order on the client account

## Message Format

### New Order (unchanged)
```
Pair: EURUSD
Type: BUY
Entry: 1.0850
SL: 1.0830
TP: 1.0900
```

### Order Modification
```
🔄 ORDER MODIFIED - Ticket #12345
Pair: EURUSD
Type: BUY
Entry: 1.0850
SL: 1.0820
TP: 1.0900

Changes:
• SL: 1.0830 → 1.0820
• TP: 1.0880 → 1.0900
```

## Features

### Master Mode Features
1. **Real-time Monitoring**: Checks for order changes every 2 seconds
2. **Change Detection**: Tracks entry, SL, TP, and volume changes
3. **Automatic Cleanup**: Removes closed/cancelled orders from tracking
4. **Detailed Logging**: Logs all detected changes

### Client Mode Features
1. **Modification Parsing**: Extracts ticket, symbol, and new values from Discord
2. **Smart Matching**: If ticket not found, searches by symbol and order type
3. **Automatic Application**: Applies changes to matching orders
4. **Fallback Logic**: Handles cases where ticket numbers differ between accounts

## Technical Details

### Files Modified
- `src/mt5_trader.py`: Added order snapshot tracking and modification detection
- `src/signal_parser.py`: Added OrderModification dataclass and parsing logic
- `src/discord_bot.py`: Added modification message handling
- `main.py`: Added modification callback and monitoring loop

### Key Methods
- `MT5Trader.check_for_order_modifications()`: Detects changes in existing orders
- `MT5Trader.modify_order()`: Applies modifications to positions/pending orders
- `MT5Trader.find_order_by_symbol()`: Finds orders by symbol when ticket not available
- `SignalParser.parse_modification()`: Parses modification messages from Discord
- `TradingBot.on_modification_received()`: Handles modification callbacks in client mode

## Usage

### Master Mode
```bash
python main.py --mode master
```
The bot will automatically detect and broadcast any order modifications you make in MT5.

### Client Mode
```bash
python main.py --mode client
```
The bot will automatically apply modifications received from the master account.

## Notes
- Ticket numbers may differ between master and client accounts
- The bot uses symbol + order type matching as a fallback
- Only orders with the configured magic number are tracked
- Modifications are applied immediately when detected
