"""
Discord Bot - Monitors channel for trading signals
"""
import discord
import logging
from typing import Callable

from src.config import TradingConfig
from src.signal_parser import SignalParser, TradingSignal, OrderModification, OrderClose
from src.session_checker import SessionChecker

logger = logging.getLogger(__name__)

class TradingDiscordBot(discord.Client):
    """Discord bot that monitors for trading signals"""
    
    def __init__(self, config: TradingConfig, on_signal: Callable[[TradingSignal], None], 
                 on_modification: Callable[[OrderModification], None] = None, 
                 on_close: Callable = None,
                 on_ready_callback=None):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(intents=intents)
        
        self.config = config
        self.on_signal = on_signal
        self.on_modification = on_modification
        self.on_close = on_close
        self.on_ready_callback = on_ready_callback
        self.parser = SignalParser()
        self.session_checker = SessionChecker(config.enabled_sessions)
        self.channel_id = config.discord_channel_id
        self.notification_channel_id = config.discord_notification_channel_id or config.discord_channel_id
        self.processed_messages = set()  # Track processed message IDs
    
    async def on_ready(self):
        try:
            logger.info(f"Discord bot logged in as {self.user}")
            logger.info(f"Monitoring channel ID: {self.channel_id}")
            logger.info(f"Notification channel ID: {self.notification_channel_id}")
            
            # Log enabled sessions
            if self.config.enabled_sessions:
                logger.info(f"Trading sessions enabled: {', '.join(self.config.enabled_sessions)}")
            else:
                logger.info("All trading sessions enabled (no filter)")
            
            # Call the ready callback if provided
            if self.on_ready_callback:
                self.on_ready_callback()
        except Exception as e:
            logger.error(f"Error in on_ready: {e}")
    
    async def send_order_notification(self, order_info: dict):
        """Send notification about new MT5 order, order modification, or order closure"""
        try:
            # Wait for bot to be ready
            logger.info(f"Attempting to send notification for order: {order_info.get('ticket', 'unknown')}")
            await self.wait_until_ready()
            logger.info(f"Bot is ready, notification channel ID: {self.notification_channel_id}")
            
            channel = self.get_channel(self.notification_channel_id)
            if not channel:
                logger.warning(f"Channel {self.notification_channel_id} not in cache, attempting to fetch...")
                # Try fetching the channel if not in cache
                try:
                    channel = await self.fetch_channel(self.notification_channel_id)
                    logger.info(f"Successfully fetched channel: {channel.name if hasattr(channel, 'name') else channel.id}")
                except Exception as e:
                    logger.error(f"Could not fetch notification channel {self.notification_channel_id}: {e}")
                    logger.error(f"Make sure the bot has access to the channel and the channel ID is correct")
                    return
            else:
                logger.info(f"Channel found in cache: {channel.name if hasattr(channel, 'name') else channel.id}")
            
            # Check if this is a close action
            if order_info.get('is_closed', False):
                trade_id = order_info.get('trade_id', f"ID#{order_info.get('ticket')}")
                message = f"""🔴 CLOSE ORDER - {trade_id}
Action: CLOSE
Trade ID: {trade_id}"""
                logger.info(f"Sending close notification for {trade_id}...")
                await channel.send(message)
                logger.info(f"✓ Successfully sent close notification for {trade_id}")
                return
            
            # Format the message for new orders or modifications
            symbol = order_info.get('symbol', 'UNKNOWN')
            order_type = order_info.get('type', 'UNKNOWN')
            price = order_info.get('price', 0.0)
            sl = order_info.get('sl', 0.0)
            tp = order_info.get('tp', 0.0)
            trade_id = order_info.get('trade_id', f"ID#{order_info.get('ticket')}")
            
            # Check if this is a modification
            if order_info.get('is_modification', False):
                changes = order_info.get('changes', [])
                message = f"""🔄 ORDER MODIFIED - {trade_id}
Pair: {symbol}
Type: {order_type}
Entry: {price}
SL: {sl}
TP: {tp}

Changes:
{chr(10).join(f"• {change}" for change in changes)}"""
            else:
                message = f"""Pair: {symbol}
Type: {order_type}
Entry: {price}
SL: {sl}
TP: {tp}
Trade ID: {trade_id}"""
            
            logger.info(f"Sending message to channel {self.notification_channel_id}...")
            await channel.send(message)
            logger.info(f"✓ Successfully sent order notification for {symbol} - {order_type}")
        except Exception as e:
            logger.error(f"Error sending order notification: {e}", exc_info=True)
    
    async def send_daily_goal_notification(self, current_percent: float, goal_percent: float, pnl_amount: float):
        """Send notification when daily profit limit is reached"""
        try:
            await self.wait_until_ready()
            
            channel = self.get_channel(self.notification_channel_id)
            if not channel:
                try:
                    channel = await self.fetch_channel(self.notification_channel_id)
                except Exception as e:
                    logger.error(f"Could not fetch notification channel: {e}")
                    return
            
            message = f"""🎯 DAILY GOAL REACHED! 🎯

Current Profit: ${pnl_amount:,.2f} ({current_percent:.2f}%)
Daily Goal: {goal_percent}%

Trading stopped for today. Great job! 💰"""
            
            await channel.send(message)
            logger.info(f"✓ Daily goal notification sent")
        except Exception as e:
            logger.error(f"Error sending daily goal notification: {e}", exc_info=True)
    
    async def on_message(self, message: discord.Message):
        try:
            # Log all messages for debugging
            logger.debug(f"Message received - Channel: {message.channel.id}, Author: {message.author.id} ({message.author.name})")
            logger.debug(f"Message content: {message.content[:200]}")
            
            # Check if we've already processed this message
            if message.id in self.processed_messages:
                logger.debug(f"Skipping already processed message ID: {message.id}")
                return
            
            # Only process messages from the configured channel
            if message.channel.id != self.channel_id:
                logger.debug(f"Ignored message from different channel: {message.channel.id} (expecting {self.channel_id})")
                return
            
            # Only process messages from authorized user (Master account)
            if message.author.id != 1479795127001157764:
                logger.warning(f"Ignored signal from unauthorized user: {message.author.id} ({message.author.name})")
                return
            
            logger.info(f"Processing message from authorized user in correct channel")
            logger.debug(f"Full message: {message.content}")
            
            # Mark message as processed
            self.processed_messages.add(message.id)
            
            # Keep only last 1000 message IDs to prevent memory growth
            if len(self.processed_messages) > 1000:
                # Remove oldest entries (convert to list, remove first 100, convert back)
                self.processed_messages = set(list(self.processed_messages)[100:])
            
            # First, try to parse as close order
            close_order = self.parser.parse_close(message.content)
            
            if close_order:
                logger.info(f"✓ Close order detected: {close_order.trade_id}")
                
                # Check break-even mode
                if self.config.break_even_mode == "copy_master":
                    logger.info(f"Break-Even Mode: COPY MASTER - Processing close order")
                    # Call the close handler
                    if self.on_close:
                        try:
                            self.on_close(close_order)
                        except Exception as e:
                            logger.error(f"Error processing close order: {e}")
                    else:
                        logger.warning("No close handler configured")
                else:
                    logger.info(f"Break-Even Mode: CUSTOM - Ignoring close order, using custom settings")
                return
            
            # Second, try to parse as order modification
            modification = self.parser.parse_modification(message.content)
            
            if modification:
                logger.info(f"✓ Order modification detected: Ticket #{modification.ticket}")
                logger.info(f"  Symbol: {modification.symbol} | Type: {modification.order_type}")
                logger.info(f"  Entry: {modification.entry_price} | SL: {modification.stop_loss} | TP: {modification.take_profit}")
                if modification.changes:
                    logger.info(f"  Changes: {', '.join(modification.changes)}")
                
                # Call the modification handler
                if self.on_modification:
                    try:
                        self.on_modification(modification)
                    except Exception as e:
                        logger.error(f"Error processing modification: {e}")
                else:
                    logger.warning("No modification handler configured")
                return
            
            # If not a modification, try to parse as trading signal
            signal = self.parser.parse(message.content)
            
            if signal:
                logger.info(f"✓ Signal detected: {signal.order_type.value} {signal.symbol}")
                logger.info(f"  Entry: {signal.entry_price} | SL: {signal.stop_loss} | TP: {signal.take_profit}")
                
                # Check if trading is allowed based on session
                is_allowed, reason = self.session_checker.is_trading_allowed()
                
                if not is_allowed:
                    logger.warning(f"❌ Signal rejected: {reason}")
                    logger.info(f"  Current time is outside enabled trading sessions")
                    return
                
                logger.info(f"✓ Session check passed: {reason}")
                
                # Call the signal handler
                if self.on_signal:
                    try:
                        self.on_signal(signal)
                    except Exception as e:
                        logger.error(f"Error processing signal: {e}")
            else:
                logger.warning("❌ Message is not a valid trading signal, modification, or close order")
                logger.debug(f"Failed to parse: {message.content}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)


