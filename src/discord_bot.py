"""
Discord Bot - Monitors channel for trading signals
"""
import discord
import logging
from typing import Callable

from src.config import TradingConfig
from src.signal_parser import SignalParser, TradingSignal, OrderModification

logger = logging.getLogger(__name__)

class TradingDiscordBot(discord.Client):
    """Discord bot that monitors for trading signals"""
    
    def __init__(self, config: TradingConfig, on_signal: Callable[[TradingSignal], None], 
                 on_modification: Callable[[OrderModification], None] = None, on_ready_callback=None):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        super().__init__(intents=intents)
        
        self.config = config
        self.on_signal = on_signal
        self.on_modification = on_modification
        self.on_ready_callback = on_ready_callback
        self.parser = SignalParser()
        self.channel_id = config.discord_channel_id
        self.notification_channel_id = config.discord_notification_channel_id or config.discord_channel_id
    
    async def on_ready(self):
        try:
            logger.info(f"Discord bot logged in as {self.user}")
            logger.info(f"Monitoring channel ID: {self.channel_id}")
            logger.info(f"Notification channel ID: {self.notification_channel_id}")
            
            # Call the ready callback if provided
            if self.on_ready_callback:
                self.on_ready_callback()
        except Exception as e:
            logger.error(f"Error in on_ready: {e}")
    
    async def send_order_notification(self, order_info: dict):
        """Send notification about new MT5 order or order modification"""
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
            
            # Format the message
            symbol = order_info.get('symbol', 'UNKNOWN')
            order_type = order_info.get('type', 'UNKNOWN')
            price = order_info.get('price', 0.0)
            sl = order_info.get('sl', 0.0)
            tp = order_info.get('tp', 0.0)
            
            # Check if this is a modification
            if order_info.get('is_modification', False):
                changes = order_info.get('changes', [])
                message = f"""🔄 ORDER MODIFIED - Ticket #{order_info.get('ticket')}
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
TP: {tp}"""
            
            logger.info(f"Sending message to channel {self.notification_channel_id}...")
            await channel.send(message)
            logger.info(f"✓ Successfully sent order notification for {symbol} - {order_type}")
        except Exception as e:
            logger.error(f"Error sending order notification: {e}", exc_info=True)
    
    async def on_message(self, message: discord.Message):
        try:
            # Log all messages for debugging
            logger.debug(f"Message received - Channel: {message.channel.id}, Author: {message.author.id} ({message.author.name})")
            logger.debug(f"Message content: {message.content[:200]}")
            
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
            
            # First, try to parse as order modification
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
                
                # Call the signal handler
                if self.on_signal:
                    try:
                        self.on_signal(signal)
                    except Exception as e:
                        logger.error(f"Error processing signal: {e}")
            else:
                logger.warning("❌ Message is not a valid trading signal or modification")
                logger.debug(f"Failed to parse: {message.content}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)


