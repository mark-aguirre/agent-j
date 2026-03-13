# Gold Trading Setup - XAUUSDc

## ✅ Your Trading Configuration

### Symbol
- **Primary Symbol**: XAUUSDc (broker-specific suffix)
- **Supported Variants**: XAUUSD, XAUUSDc, XAUUSDT, XAUUSDC
- **Auto-detection**: ✅ The bot automatically finds your broker's gold symbol

### Order Types
- **Market Orders**: BUY, SELL
- **No Pending Orders**: You're using instant execution only
- **SL/TP**: 0.0 (no stop loss or take profit set initially)

### Sample Signals from Your Trading

```
Pair: XAUUSDc
Type: SELL
Entry: 5107.316
SL: 0.0
TP: 0.0
Trade ID: ID#123456
```

```
Pair: XAUUSDc
Type: BUY
Entry: 5104.343
SL: 0.0
TP: 0.0
Trade ID: ID#789012
```

```
Pair: XAUUSDc
Type: BUY
Entry: 5104.145
SL: 0.0
TP: 0.0
Trade ID: ID#345678
```

```
Pair: XAUUSDc
Type: BUY
Entry: 5094.404
SL: 0.0
TP: 0.0
Trade ID: ID#999888
```

## 🎯 How It Works for Your Gold Trading

### 1. Master Mode (Your EA or Manual Trading)
```
1. EA creates BUY order on XAUUSDc @ 5104.343
   ↓
2. Bot detects new position
   ↓
3. Bot adds Trade ID to comment: "ID#123456"
   ↓
4. Bot sends to Discord:
   Pair: XAUUSDc
   Type: BUY
   Entry: 5104.343
   SL: 0.0
   TP: 0.0
   Trade ID: ID#123456
```

### 2. Client Mode (Copy Trading Accounts)
```
1. Client receives signal from Discord
   ↓
2. Client creates BUY order on XAUUSDc @ 5104.343
   ↓
3. Client stores master Trade ID in comment: "ID#123456"
   ↓
4. Orders are now linked
```

### 3. When You Modify SL/TP
```
Master: Changes SL from 0.0 to 5100.00
   ↓
Bot detects modification
   ↓
Sends to Discord:
   🔄 ORDER MODIFIED - ID#123456
   Pair: XAUUSDc
   Type: BUY
   Entry: 5104.343
   SL: 5100.00
   TP: 0.0
   Changes:
   • SL: 0.0 → 5100.00
   ↓
Client finds order by ID#123456
   ↓
Client updates SL to 5100.00
```

### 4. When You Close Position
```
Master: Closes position ID#123456
   ↓
Bot detects closure
   ↓
Sends to Discord:
   🔴 CLOSE ORDER - ID#123456
   Action: CLOSE
   Trade ID: ID#123456
   ↓
Client finds order by ID#123456
   ↓
Client closes matching position
```

## ⚙️ Configuration for Gold Trading

### Spread Settings
```env
MAX_SPREAD_GOLD=500
```
- Gold typically has higher spreads than forex
- Default: 500 points (5.00 on XAUUSDc)
- Adjust based on your broker's typical spread

### Risk Management
Since you're trading without SL/TP initially:

```env
# Risk per trade (percentage of equity)
RISK_PERCENT=1.0

# Or use fixed lot size
FIXED_LOT=0.01

# Maximum open trades
MAX_OPEN_TRADES=10
```

### Gold-Specific Settings

**Pip Calculation:**
- For XAUUSD: 1 pip = 0.01 (e.g., 5104.34 to 5104.35)
- The bot automatically handles this

**Break-Even & Trailing Stop:**
```env
# Break-even (in pips for gold)
USE_BREAK_EVEN=true
BREAK_EVEN_AT_PIPS=300.0    # Move to BE after 3.00 profit
BREAK_EVEN_OFFSET_PIPS=100.0 # Set BE at entry + 1.00

# Trailing stop (in pips for gold)
USE_TRAILING_STOP=true
TRAILING_START_PIPS=500.0    # Start trailing after 5.00 profit
TRAILING_STEP_PIPS=100.0     # Trail by 1.00
```

## 🔍 Symbol Detection

The bot will automatically find your broker's gold symbol:

**Supported Formats:**
- XAUUSD
- XAUUSDc (your broker)
- XAUUSDT
- XAUUSDC
- XAUUSD.m
- XAUUSD_sb
- Any other suffix your broker uses

**How it works:**
1. Bot tries exact match: "XAUUSDc"
2. If not found, tries common suffixes
3. If still not found, searches all symbols for "XAUUSD"

## 📊 Multiple Positions

Your example shows multiple BUY positions on gold:
```
Position 1: BUY @ 5104.343 - ID#123456
Position 2: BUY @ 5104.145 - ID#789012
Position 3: BUY @ 5094.404 - ID#345678
```

**Each position gets a unique Trade ID**, so:
- Master can modify each independently
- Master can close each independently
- Clients will match and sync each position correctly

## ✅ Verification Checklist

### Master Mode Setup:
- [ ] MT5 connected with your gold account
- [ ] Discord bot token configured
- [ ] Notification channel ID set
- [ ] Run: `python main.py --mode master`
- [ ] Create a test gold position
- [ ] Verify Trade ID appears in MT5 comment
- [ ] Verify signal appears in Discord

### Client Mode Setup:
- [ ] MT5 connected with copy account
- [ ] Discord bot token configured
- [ ] Channel ID set (same as master's notification channel)
- [ ] Run: `python main.py --mode client`
- [ ] Wait for master signal
- [ ] Verify position is created
- [ ] Verify master Trade ID is in comment

### Synchronization Test:
- [ ] Master creates gold position → Client creates position ✅
- [ ] Master modifies SL/TP → Client modifies SL/TP ✅
- [ ] Master closes position → Client closes position ✅

## 🎯 Key Points for Your Setup

1. **No SL/TP Initially**: ✅ Supported (defaults to 0.0)
2. **Market Orders Only**: ✅ Fully supported
3. **Multiple Positions**: ✅ Each gets unique Trade ID
4. **Gold Symbol (XAUUSDc)**: ✅ Auto-detected
5. **Broker Suffix**: ✅ Handled automatically
6. **High Precision Prices**: ✅ Supports decimal places (5104.343)

## 🚀 Ready to Use

Your implementation is **100% aligned** with your gold trading strategy:
- ✅ Handles XAUUSDc symbol
- ✅ Supports SL/TP = 0.0
- ✅ Works with market orders
- ✅ Manages multiple positions
- ✅ Synchronizes all actions (create, modify, close)

Just configure your environment variables and run in master/client mode!
