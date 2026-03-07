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
from src.signal_parser import TradingSignal
from src.mt5_trader import MT5Trader
from src.discord_bot import TradingDiscordBot

# Create logs directory if it doesn't exist
log_dir = Path('logs')
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
            logger.info("=" * 50)
            
            # Execute the trade
            result = self.trader.execute_signal(signal)
            
            if result.success:
                logger.info(f"[OK] Trade executed! Ticket: {result.ticket} | Lot: {result.lot_size}")
            else:
                logger.error(f"[FAILED] Trade failed: {result.message}")
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def position_manager_loop(self):
        """Background loop to manage open positions"""
        while self.running:
            try:
                self.trader.manage_positions()
            except Exception as e:
                logger.error(f"Error in position manager: {e}")
            await asyncio.sleep(1)  # Check every second
    
    async def order_monitor_loop(self):
        """Background loop to monitor for new MT5 orders and send Discord notifications"""
        logger.info("Order monitor loop started")
        while self.running:
            try:
                new_orders = self.trader.check_for_new_orders()
                
                if new_orders:
                    logger.info(f"Found {len(new_orders)} new order(s)")
                    if self.discord_bot:
                        for order_info in new_orders:
                            logger.info(f"Processing order: {order_info}")
                            await self.discord_bot.send_order_notification(order_info)
                    else:
                        logger.error("Discord bot is None, cannot send notifications")
                        
            except Exception as e:
                logger.error(f"Error in order monitor: {e}", exc_info=True)
            await asyncio.sleep(2)  # Check every 2 seconds
    
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
        
        if self.mode == "master":
            logger.info("Mode: MASTER - Sending signals & managing positions")
        else:
            logger.info("Mode: CLIENT - Monitoring signals & creating orders")
        
        logger.info("=" * 50)
        
        self.running = True
        
        # Start position manager (both modes)
        position_task = asyncio.create_task(self.position_manager_loop())
        
        if self.mode == "master":
            # MASTER MODE: Monitor MT5 orders and send signals to Discord
            # Initialize Discord bot for sending signals
            self.discord_bot = TradingDiscordBot(self.config, None, 
                                                 on_ready_callback=lambda: setattr(self, 'discord_ready', True))
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
                if order_monitor_task:
                    order_monitor_task.cancel()
                if discord_task:
                    discord_task.cancel()
                if self.discord_bot:
                    await self.discord_bot.close()
                self.trader.disconnect()
        else:
            # CLIENT MODE: Monitor Discord and execute trades (NO signal sending)
            self.discord_bot = TradingDiscordBot(self.config, self.on_signal_received, 
                                                 on_ready_callback=lambda: setattr(self, 'discord_ready', True))
            
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
