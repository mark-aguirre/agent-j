# Trading Sessions Feature

## Overview
The trading sessions feature allows you to filter Discord signals based on specific forex market sessions. When enabled, the bot will only process signals during the selected trading sessions.

## Available Sessions (Philippines Time - UTC+8)

| Session | Country | Time Range | Emoji |
|---------|---------|------------|-------|
| Sydney Session | Australia | 6:00 AM - 3:00 PM | 🌏 |
| Tokyo Session (Asian) | Japan | 8:00 AM - 5:00 PM | 🌏 |
| London Session | United Kingdom | 4:00 PM - 1:00 AM | 🇬🇧 |
| New York Session | United States | 9:00 PM - 6:00 AM | 🇺🇸 |

## How to Use

### In the GUI Settings Tab:
1. Navigate to the **Settings** tab
2. Scroll down to the **Trading Sessions (Philippines Time)** section
3. Check the sessions you want to enable
4. Settings are automatically saved when you check/uncheck a session

### Behavior:
- **No sessions selected**: Bot will process all signals (no filtering)
- **One or more sessions selected**: Bot will only process signals during those sessions
- **Outside session hours**: Signals are rejected with a log message

## Example Use Cases

### London Session Only
If you only want to trade during the London session:
- ✅ Check: London Session
- ❌ Uncheck: Sydney, Tokyo, New York

The bot will only process signals between 4:00 PM and 1:00 AM Philippines time.

### London + New York Overlap
For the high-volume overlap period:
- ✅ Check: London Session
- ✅ Check: New York Session
- ❌ Uncheck: Sydney, Tokyo

The bot will process signals during both sessions (4:00 PM - 6:00 AM).

### Asian Sessions
For Asian market hours:
- ✅ Check: Sydney Session
- ✅ Check: Tokyo Session
- ❌ Uncheck: London, New York

## Configuration File

Sessions are stored in the `.env` file as:
```
ENABLED_SESSIONS=London,New York
```

Multiple sessions are comma-separated.

## Logging

When a signal is received:
- ✅ **Accepted**: `✓ Session check passed: Active session: London`
- ❌ **Rejected**: `❌ Signal rejected: Outside trading hours. Enabled sessions: 🇬🇧 London`

## Technical Details

- Session times are checked using Philippines local time (UTC+8)
- Sessions that cross midnight (like New York: 9:00 PM - 6:00 AM) are handled correctly
- Order modifications are NOT filtered by session (they always process)
- Session checker is initialized when the bot starts
