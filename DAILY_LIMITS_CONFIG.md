# Daily Limits Configuration

The bot supports configurable daily limits to protect your account from excessive losses or to lock in profits when targets are reached.

## Configuration Options

Add these settings to your `.env` file:

```env
# Daily Limits
USE_DAILY_LIMITS=true
MAX_DAILY_LOSS_PERCENT=3.0
MAX_DAILY_PROFIT_PERCENT=5.0
MAX_DAILY_TRADES=5
```

## Settings Explained

### USE_DAILY_LIMITS
- **Type**: Boolean (true/false)
- **Default**: true
- **Description**: Enable or disable daily limits protection

### MAX_DAILY_LOSS_PERCENT
- **Type**: Float
- **Default**: 3.0
- **Description**: Maximum daily loss percentage before bot stops trading
- **Example**: 3.0 means bot stops if you lose 3% of your daily starting balance

### MAX_DAILY_PROFIT_PERCENT
- **Type**: Float
- **Default**: 5.0
- **Description**: Daily profit target - bot stops trading when reached to lock in profits
- **Example**: 5.0 means bot stops if you gain 5% of your daily starting balance
- **Note**: A Discord notification is sent when this target is reached

### MAX_DAILY_TRADES
- **Type**: Integer
- **Default**: 5
- **Description**: Maximum number of trades allowed per day

## How It Works

1. The bot tracks your account balance at the start of each trading day
2. After each trade, it calculates your daily P&L percentage
3. If you reach the loss limit (e.g., -3%), the bot stops accepting new trades
4. If you reach the profit target (e.g., +5%), the bot stops and sends a notification
5. If you reach the max trades limit, the bot stops for the day
6. Limits reset at the start of the next trading day

## GUI Configuration

You can also configure these settings through the Settings tab in the GUI:

1. Open the bot
2. Go to Settings tab
3. Find the "Daily Limits" section
4. Toggle "Enabled" checkbox
5. Adjust the loss/profit percentages and trade count
6. Settings auto-save when changed

## Example Scenarios

### Conservative Trading
```env
MAX_DAILY_LOSS_PERCENT=2.0
MAX_DAILY_PROFIT_PERCENT=3.0
MAX_DAILY_TRADES=3
```

### Aggressive Trading
```env
MAX_DAILY_LOSS_PERCENT=5.0
MAX_DAILY_PROFIT_PERCENT=10.0
MAX_DAILY_TRADES=10
```

### Disable Limits
```env
USE_DAILY_LIMITS=false
```

## Notes

- Daily limits are calculated based on your account balance at the start of the day
- The bot will log warnings when limits are reached
- Existing open positions are not affected when limits are reached
- Only new trade signals will be rejected
- A Discord notification is automatically sent when the profit target is reached
