# Trade ID Mapping Fix

## Problem

Client orders were not being identified correctly when receiving close signals from the master because:

1. The Trade ID was initially stored in the order comment: `Discord-Signal ID#2835761802`
2. When breakeven/trailing stop modified the SL/TP, MT5's `TRADE_ACTION_SLTP` doesn't preserve comments
3. The broker overwrites the comment with its own format: `Discord-Signal[sl 5106.76400]`
4. The original Trade ID is lost, making it impossible to match close signals

## Solution

Implemented a **persistent Trade ID mapping system** that:

1. **Stores mappings in memory**: `{client_ticket: master_trade_id}`
2. **Persists to file**: `trade_id_mapping.json` (survives bot restarts)
3. **Multi-layer lookup strategy**:
   - First checks the in-memory mapping (fastest, most reliable)
   - Falls back to searching order comments (for orders placed before this fix)
   - Automatically adds discovered mappings to the persistent storage

## How It Works

### When Client Receives a Signal

```python
# 1. Parse signal and extract Trade ID
signal = parser.parse(message)  # signal.trade_id = "ID#2835761802"

# 2. Place order
result = mt5.order_send(request)

# 3. Store mapping
trade_id_map[result.order] = signal.trade_id  # {123456: "ID#2835761802"}
_save_trade_id_map()  # Save to trade_id_mapping.json
```

### When Client Receives Close Signal

```python
# 1. Parse close signal
close_order = parser.parse_close(message)  # close_order.trade_id = "ID#2835761802"

# 2. Find client ticket using mapping
client_ticket = find_order_by_master_trade_id("ID#2835761802")
# Checks: trade_id_map -> returns 123456

# 3. Close the order
close_position(client_ticket)
```

## Files Modified

1. **src/mt5_trader.py**:
   - Added `trade_id_map` dictionary
   - Added `_load_trade_id_map()` and `_save_trade_id_map()` methods
   - Updated `execute_signal()` to store mappings
   - Updated `find_order_by_master_trade_id()` to use mapping first

2. **main.py**:
   - Added warning log when signal has no Trade ID

## Benefits

- ✅ Works even when broker modifies comments
- ✅ Survives bot restarts (persistent storage)
- ✅ Backward compatible (still checks comments as fallback)
- ✅ Automatic cleanup (removes mappings for closed orders)
- ✅ Fast lookups (in-memory dictionary)

## Testing

1. Start the client bot
2. Receive a signal from master with Trade ID
3. Check `trade_id_mapping.json` file is created
4. Let breakeven/trailing stop modify the order
5. Receive close signal from master
6. Verify the order is closed correctly

## Logs to Watch

```
Adding master trade ID to comment: ID#2835761802
Final comment will be: 'Discord-Signal ID#2835761802'
Order placed with comment: 'Discord-Signal ID#2835761802'
Stored trade ID mapping: 123456 -> ID#2835761802
```

When closing:
```
Searching for order with master trade ID ID#2835761802 in comment...
Found position 123456 with master trade ID ID#2835761802 (from mapping)
[OK] Position 123456 closed successfully
```
