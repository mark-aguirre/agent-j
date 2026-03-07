import MetaTrader5 as mt5

mt5.initialize()

symbol = "BTCUSD"
mt5.symbol_select(symbol, True)

tick = mt5.symbol_info_tick(symbol)
info = mt5.symbol_info(symbol)

if tick and info:
    spread = int((tick.ask - tick.bid) / info.point)
    print(f"Symbol: {symbol}")
    print(f"Bid: {tick.bid}")
    print(f"Ask: {tick.ask}")
    print(f"Point: {info.point}")
    print(f"Spread: {spread} points")
else:
    print("Failed to get info")

mt5.shutdown()
