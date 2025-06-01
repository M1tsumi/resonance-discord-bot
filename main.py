import discord
from discord.ext import commands
import config
import asyncio
import aiosqlite
import logging
import os
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DiscordBot')

class AdvancedBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            case_insensitive=True,
            help_command=None  # We'll create a custom help command
        )
        self.db = None
        self.config = config
        self.start_time = datetime.utcnow()
        
    async def get_prefix(self, message):
        # Default prefix
        prefix = config.DEFAULT_PREFIX
        
        # If DM, return default prefix
        if not message.guild:
            return prefix
            
        # Get custom prefix from database if exists
        async with self.db.execute(
            "SELECT prefix FROM guild_settings WHERE guild_id = ?",
            (message.guild.id,)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                prefix = result[0]
                
        return commands.when_mentioned_or(prefix)(self, message)

    async def setup_hook(self):
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        # Initialize database connection
        self.db = await aiosqlite.connect(config.DATABASE_PATH)
        
        # Create necessary tables
        await self.init_db()
        
        # Load extensions
        await self.load_extensions()
        
        logger.info("Bot is ready to start!")

    async def init_db(self):
        # Create tables for various features
        async with self.db.cursor() as cursor:
            # Guild settings
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    prefix TEXT DEFAULT '!',
                    welcome_channel_id INTEGER,
                    log_channel_id INTEGER,
                    welcome_message TEXT,
                    leveling_enabled BOOLEAN DEFAULT 1,
                    automod_enabled BOOLEAN DEFAULT 1
                )
            """)
            
            # Leveling system
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS levels (
                    user_id INTEGER,
                    guild_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 0,
                    last_xp_time TEXT,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            # Warnings
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    moderator_id INTEGER,
                    reason TEXT,
                    timestamp TEXT
                )
            """)
            
            # Custom commands
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_commands (
                    guild_id INTEGER,
                    command_name TEXT,
                    response TEXT,
                    creator_id INTEGER,
                    created_at TEXT,
                    PRIMARY KEY (guild_id, command_name)
                )
            """)
            
            # Role rewards
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS role_rewards (
                    guild_id INTEGER,
                    role_id INTEGER,
                    level_requirement INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            
        await self.db.commit()

    async def load_extensions(self):
        """Load all cogs from the cogs directory."""
        for filename in os.listdir("cogs"):
            if filename.endswith(".py"):
                # Skip music cog for now
                if filename == "music.py":
                    continue
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    logger.info(f"Loaded extension: {filename[:-3]}")
                except Exception as e:
                    logger.error(f"Failed to load extension {filename[:-3]}: {e}")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        logger.info(f'Connected to {len(self.guilds)} guilds')
        
        # Set custom status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{config.DEFAULT_PREFIX}help | {len(self.guilds)} servers"
            )
        )

    async def on_guild_join(self, guild):
        """Initialize guild settings when bot joins a new server."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
                (guild.id,)
            )
        await self.db.commit()
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

    async def close(self):
        """Cleanup before bot shutdown."""
        if self.db:
            await self.db.close()
        await super().close()

async def main():
    """Main function to start the bot."""
    async with AdvancedBot() as bot:
        try:
            await bot.start(config.TOKEN)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}") 