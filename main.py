"""
Discord Trading Bot - Main Entry Point
Supports two modes:
- MASTER: Sends signals to Discord and manages breakeven/trailing stop
- CLIENT: Monitors Discord signals, creates orders, and manages breakeven/trailing stop
"""
import asyncio
import logging
import sys
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

from src.__version__ import __version__, __app_name__
from src.config import load_config, TradingConfig
from src.signal_parser import TradingSignal, OrderModification, OrderClose
from src.mt5_trader import MT5Trader
from src.discord_bot import TradingDiscordBot

# Create logs directory if it doesn't exist
# Use the directory where the script/executable is located
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    # Use _MEIPASS for PyInstaller or executable parent directory
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller temp directory - use executable's parent instead
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(sys.executable).parent
    
    # Ensure we're not in system32 or other system directories
    if 'system32' in str(app_dir).lower() or 'windows' in str(app_dir).lower():
        # Fall back to user's documents or current working directory
        app_dir = Path.cwd()
else:
    # Running as script
    app_dir = Path(__file__).parent

log_dir = app_dir / 'logs'
log_dir.mkdir(exist_ok=True)

# Setup logging with UTF-8 encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / 'trading_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    """Main trading bot that supports both MASTER and CLIENT modes"""
    
    def __init__(self, config: TradingConfig, mode: str = "client"):
        self.config = config
        self.mode = mode.lower()
        self.trader = MT5Trader(config)
        self.discord_bot = None
        self.running = False
        self.signal_queue = asyncio.Queue()
        self.discord_ready = False
    
    def on_signal_received(self, signal: TradingSignal):
        """Callback when Discord signal is received"""
        try:
            logger.info("=" * 50)
            logger.info(f"SIGNAL RECEIVED: {signal.order_type.value.upper()} {signal.symbol}")
            logger.info(f"Entry: {signal.entry_price}")
            logger.info(f"SL: {signal.stop_loss} ({signal.sl_pips:.1f} pips)")
            logger.info(f"TP: {signal.take_profit} ({signal.tp_pips:.1f} pips)")
            if signal.trade_id:
                logger.info(f"Master Trade ID: {signal.trade_id}")
            else:
                logger.warning(f"NO TRADE ID IN SIGNAL!")
            logger.info("=" * 50)
            
            # Execute the trade
            result = self.trader.execute_signal(signal)
            
            if result.success:
                logger.info(f"[OK] Trade executed! Ticket: {result.ticket} | Lot: {result.lot_size}")
                if signal.trade_id:
                    logger.info(f"Linked to master trade: {signal.trade_id}")
            else:
                logger.error(f"[FAILED] Trade failed: {result.message}")
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    def on_close_received(self, close_order: OrderClose):
        """Callback when Discord close order is received"""
        try:
            logger.info("=" * 50)
            logger.info(f"CLOSE ORDER RECEIVED: {close_order.trade_id}")
            logger.info("=" * 50)
            
            client_ticket = None
            
            # Strategy 1: Try to find by master trade ID in comment
            logger.info(f"Searching for order with master trade ID {close_order.trade_id} in comment...")
            client_ticket = self.trader.find_order_by_master_trade_id(close_order.trade_id)
            
            # Strategy 2: Try to find by master ticket in comment (fallback)
            if not client_ticket:
                logger.info(f"Searching for order with master ticket {close_order.ticket} in comment...")
                client_ticket = self.trader.find_order_by_master_ticket(close_order.ticket)
            
            if client_ticket:
                logger.info(f"Found client order: {client_ticket}")
                
                # Check if it's a position or pending order
                import MetaTrader5 as mt5
                positions = mt5.positions_get(ticket=client_ticket)
                if positions:
                    # Close position
                    success = self.trader.close_position(client_ticket)
                    if success:
                        logger.info(f"[OK] Position {client_ticket} closed successfully")
                    else:
                        logger.error(f"[FAILED] Failed to close position {client_ticket}")
                else:
                    # Cancel pending order
                    success = self.trader.cancel_order(client_ticket)
                    if success:
                        logger.info(f"[OK] Pending order {client_ticket} cancelled successfully")
                    else:
                        logger.error(f"[FAILED] Failed to cancel pending order {client_ticket}")
            else:
                logger.warning(f"[NOT FOUND] No matching order found for {close_order.trade_id}")
                
        except Exception as e:
            logger.error(f"Error processing close order: {e}")
    
    def on_modification_received(self, modification: OrderModification):
        """Callback when Discord order modification is received"""
        try:
            logger.info("=" * 50)
            logger.info(f"MODIFICATION RECEIVED: {modification.trade_id if modification.trade_id else f'Ticket #{modification.ticket}'}")
            logger.info(f"Symbol: {modification.symbol} | Type: {modification.order_type}")
            logger.info(f"Entry: {modification.entry_price}")
            logger.info(f"SL: {modification.stop_loss}")
            logger.info(f"TP: {modification.take_profit}")
            if modification.changes:
                logger.info(f"Changes: {', '.join(modification.changes)}")
            logger.info("=" * 50)
            
            client_ticket = None
            
            # Strategy 1: Try to find by master trade ID in comment
            if modification.trade_id:
                logger.info(f"Searching for order with master trade ID {modification.trade_id} in comment...")
                client_ticket = self.trader.find_order_by_master_trade_id(modification.trade_id)
            
            # Strategy 2: Try to find by master ticket in comment (fallback)
            if not client_ticket:
                logger.info(f"Searching for order with master ticket {modification.ticket} in comment...")
                client_ticket = self.trader.find_order_by_master_ticket(modification.ticket)
            
            # Strategy 3: If not found, search by symbol, order type, and entry price
            if not client_ticket:
                logger.info(f"Master reference not found in comments, searching by symbol/type/entry...")
                client_ticket = self.trader.find_order_by_symbol_ordertype_and_entry(
                    modification.symbol, 
                    modification.order_type,
                    modification.entry_price
                )
            
            if client_ticket:
                logger.info(f"Found client order: {client_ticket}")
                success = self.trader.modify_order(
                    ticket=client_ticket,
                    entry=modification.entry_price,
                    sl=modification.stop_loss,
                    tp=modification.take_profit,
                    master_trade_id=modification.trade_id  # Store master trade ID in comment
                )
                
                if success:
                    logger.info(f"[OK] Order modified successfully")
                else:
                    logger.error(f"[FAILED] Failed to modify order")
            else:
                logger.error(f"[FAILED] No matching order found for modification")
                
        except Exception as e:
            logger.error(f"Error processing modification: {e}")
    
    async def position_manager_loop(self):
        """Background loop to manage open positions"""
        while self.running:
            try:
                self.trader.manage_positions()
                # Check for closed positions to update martingale state
                self.trader._check_closed_positions()
            except Exception as e:
                logger.error(f"Error in position manager: {e}")
            await asyncio.sleep(0.1)  # Check every 100ms
    
    async def order_monitor_loop(self):
        """Background loop to monitor for new MT5 orders and modifications, then send Discord notifications"""
        logger.info("Order monitor loop started")
        while self.running:
            try:
                # Check for new orders
                new_orders = self.trader.check_for_new_orders()
                
                if new_orders:
                    logger.info(f"Found {len(new_orders)} new order(s)")
                    if self.discord_bot:
                        for order_info in new_orders:
                            logger.info(f"Processing new order: {order_info}")
                            await self.discord_bot.send_order_notification(order_info)
                    else:
                        logger.error("Discord bot is None, cannot send notifications")
                
                # Check for order modifications
                modified_orders = self.trader.check_for_order_modifications()
                
                if modified_orders:
                    logger.info(f"Found {len(modified_orders)} modified order(s)")
                    if self.discord_bot:
                        for order_info in modified_orders:
                            logger.info(f"Processing modified order: {order_info}")
                            await self.discord_bot.send_order_notification(order_info)
                    else:
                        logger.error("Discord bot is None, cannot send notifications")
                        
            except Exception as e:
                logger.error(f"Error in order monitor: {e}", exc_info=True)
            await asyncio.sleep(0.5)  # Check every 500ms
    
    async def daily_goal_monitor_loop(self):
        """Background loop to monitor daily profit limit and send notification when reached"""
        logger.info("Daily profit monitor loop started")
        while self.running:
            try:
                goal_reached, current_percent, pnl_amount = self.trader.get_daily_goal_status()
                
                # Send notification only once when profit limit is reached
                if goal_reached and not self.trader.daily_goal_notified:
                    logger.info(f"Daily profit limit reached! Sending notification...")
                    if self.discord_bot:
                        await self.discord_bot.send_daily_goal_notification(
                            current_percent, 
                            self.config.max_daily_profit_percent,
                            pnl_amount
                        )
                        self.trader.daily_goal_notified = True
                    else:
                        logger.warning("Discord bot is None, cannot send daily goal notification")
                        
            except Exception as e:
                logger.error(f"Error in daily goal monitor: {e}", exc_info=True)
            await asyncio.sleep(5)  # Check every 5 seconds
    
    async def run(self):
        """Main run loop"""
        # Connect to MT5
        if not self.trader.connect():
            logger.error("Failed to connect to MT5. Exiting.")
            return
        
        logger.info("=" * 50)
        logger.info(f"{__app_name__} v{__version__}")
        logger.info(f"Discord Trading Bot Started - {self.mode.upper()} MODE")
        logger.info(f"Account Balance: ${self.trader.get_balance():.2f}")
        logger.info(f"Risk Mode: {self.config.risk_mode.value}")
        logger.info(f"Risk Per Trade: {self.config.risk_percent}%")
        logger.info(f"Max Daily Trades: {self.config.max_daily_trades}")
        logger.info(f"Break-Even: {'Enabled' if self.config.use_break_even else 'Disabled'} "
                   f"(Activate: {self.config.break_even_at_pips} pips, Offset: {self.config.break_even_offset_pips} pips)")
        logger.info(f"Trailing Stop: {'Enabled' if self.config.use_trailing_stop else 'Disabled'} "
                   f"(Start: {self.config.trailing_start_pips} pips, Step: {self.config.trailing_step_pips} pips)")
        logger.info(f"Daily Limits: {'Enabled' if self.config.use_daily_limits else 'Disabled'} "
                   f"(Loss: {self.config.max_daily_loss_percent}%, Profit: {self.config.max_daily_profit_percent}%, Max Trades: {self.config.max_daily_trades})")
        logger.info(f"Martingale: {'Enabled' if self.config.use_martingale else 'Disabled'} "
                   f"(Base Lot: {self.config.martingale_base_lot}, Multiplier: {self.config.martingale_multiplier}x, Max Losses: {self.config.martingale_max_losses})")
        
        if self.mode == "master":
            logger.info("Mode: MASTER - Sending signals & managing positions")
        else:
            logger.info("Mode: CLIENT - Monitoring signals & creating orders")
        
        logger.info("=" * 50)
        
        self.running = True
        
        # Start position manager (both modes)
        position_task = asyncio.create_task(self.position_manager_loop())
        
        # Start daily goal monitor (both modes)
        daily_goal_task = asyncio.create_task(self.daily_goal_monitor_loop())
        
        if self.mode == "master":
            # MASTER MODE: Monitor MT5 orders and send signals to Discord
            # Initialize Discord bot for sending signals (no callbacks needed in master mode)
            self.discord_bot = TradingDiscordBot(
                self.config, 
                on_signal=None,
                on_modification=None,
                on_close=None,
                on_ready_callback=lambda: setattr(self, 'discord_ready', True)
            )
            order_monitor_task = None
            discord_task = None
            
            try:
                # Start Discord bot in background
                discord_task = asyncio.create_task(self.discord_bot.start(self.config.discord_token))
                
                # Give Discord a moment to start connecting
                await asyncio.sleep(2)
                
                # Wait for Discord bot to be ready before starting order monitor
                logger.info("Waiting for Discord bot to connect...")
                try:
                    await asyncio.wait_for(self.discord_bot.wait_until_ready(), timeout=10.0)
                    logger.info("Discord bot ready! Starting order monitor...")
                except asyncio.TimeoutError:
                    logger.error("Discord bot failed to connect within 10 seconds")
                    return
                
                # Now start order monitor after Discord is ready
                order_monitor_task = asyncio.create_task(self.order_monitor_loop())
                
                # Keep running and managing positions
                while self.running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
            finally:
                self.running = False
                position_task.cancel()
                daily_goal_task.cancel()
                if order_monitor_task:
                    order_monitor_task.cancel()
                if discord_task:
                    discord_task.cancel()
                if self.discord_bot:
                    await self.discord_bot.close()
                self.trader.disconnect()
        else:
            # CLIENT MODE: Monitor Discord and execute trades (NO signal sending)
            self.discord_bot = TradingDiscordBot(
                self.config, 
                self.on_signal_received,
                self.on_modification_received,
                self.on_close_received,
                on_ready_callback=lambda: setattr(self, 'discord_ready', True)
            )
            
            try:
                # Run Discord bot (this blocks)
                await self.discord_bot.start(self.config.discord_token)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
            except Exception as e:
                logger.error(f"Discord bot error: {e}")
            finally:
                self.running = False
                try:
                    position_task.cancel()
                except Exception as e:
                    logger.error(f"Error cancelling position task: {e}")
                try:
                    daily_goal_task.cancel()
                except Exception as e:
                    logger.error(f"Error cancelling daily goal task: {e}")
                try:
                    if self.discord_bot:
                        await self.discord_bot.close()
                except Exception as e:
                    logger.error(f"Error closing Discord bot: {e}")
                try:
                    self.trader.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting from MT5: {e}")

def main():
    """Entry point"""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(
            description=f'{__app_name__} v{__version__}',
            epilog='Discord Trading Bot with MT5 Integration'
        )
        parser.add_argument('--mode', type=str, choices=['master', 'client'], 
                          default='client', help='Bot mode: master or client')
        parser.add_argument('--mt5-password', type=str, 
                          help='MT5 account password (overrides .env)')
        parser.add_argument('--version', action='version', 
                          version=f'{__app_name__} v{__version__}')
        args = parser.parse_args()
        
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        config = load_config()
        
        # Override MT5 password if provided via command line
        if args.mt5_password:
            config.mt5_password = args.mt5_password
            logger.info("Using MT5 password from command line argument")
        
        # Validate config based on mode
        if args.mode == 'client':
            if not config.discord_token:
                logger.error("DISCORD_TOKEN not set in environment")
                sys.exit(1)
            
            if not config.discord_channel_id:
                logger.error("DISCORD_CHANNEL_ID not set in environment")
                sys.exit(1)
        
        # Create and run bot
        bot = TradingBot(config, mode=args.mode)
        
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
