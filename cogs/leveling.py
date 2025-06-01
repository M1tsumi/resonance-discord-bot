import discord
from discord.ext import commands, tasks
import config
from datetime import datetime, timedelta
import math
import asyncio
from typing import Dict, Set
import random
import json

class LevelingSystem:
    def __init__(self):
        self.xp_cache = {}
        self.active_drops = {}
        self.reaction_cooldowns = set()
        self.voice_xp_cooldowns = {}

    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a specific level."""
        return math.floor(100 * (level ** 1.5))

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate level from total XP."""
        return math.floor((xp / 100) ** (1 / 1.5))

class Leveling(commands.Cog):
    """XP and leveling system with multiple ways to earn XP."""

    def __init__(self, bot):
        self.bot = bot
        self.system = LevelingSystem()
        self.xp_tasks = {
            'voice_xp': self.voice_xp_task,
            'drop_spawn': self.drop_spawn_task
        }
        self.start_tasks()

    def start_tasks(self):
        """Start all background tasks."""
        for task in self.xp_tasks.values():
            task.start()

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        for task in self.xp_tasks.values():
            task.cancel()

    async def create_level_card(self, member: discord.Member, xp: int, level: int, rank: int) -> discord.File:
        """Create a visual level card for the user."""
        # TODO: Implement visual card generation
        return None

    async def add_xp(self, user_id: int, guild_id: int, xp_amount: int, source: str = "message"):
        """Add XP to a user and handle level ups."""
        async with self.bot.db.cursor() as cursor:
            # Get current XP and level
            await cursor.execute("""
                SELECT xp, level FROM levels
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            result = await cursor.fetchone()
            
            if result:
                current_xp, current_level = result
            else:
                current_xp, current_level = 0, 0
                await cursor.execute("""
                    INSERT INTO levels (user_id, guild_id, xp, level)
                    VALUES (?, ?, 0, 0)
                """, (user_id, guild_id))

            # Add XP
            new_xp = current_xp + xp_amount
            new_level = self.system.calculate_level_from_xp(new_xp)

            # Update database
            await cursor.execute("""
                UPDATE levels
                SET xp = ?, level = ?, last_xp_time = ?
                WHERE user_id = ? AND guild_id = ?
            """, (new_xp, new_level, datetime.utcnow().isoformat(), user_id, guild_id))

            # Log XP gain
            await cursor.execute("""
                INSERT INTO xp_logs (user_id, guild_id, xp_amount, source, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, guild_id, xp_amount, source, datetime.utcnow().isoformat()))

        await self.bot.db.commit()

        # Handle level up
        if new_level > current_level:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            
            member = guild.get_member(user_id)
            if not member:
                return

            # Check for role rewards
            async with self.bot.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT role_id FROM role_rewards
                    WHERE guild_id = ? AND level_requirement <= ?
                    ORDER BY level_requirement DESC
                """, (guild_id, new_level))
                role_rewards = await cursor.fetchall()

            for role_id, in role_rewards:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Level {new_level} reward")
                    except discord.HTTPException:
                        continue

            # Create level up embed
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"Congratulations {member.mention}! You've reached level {new_level}!",
                color=discord.Color.gold()
            )
            
            # Progress to next level
            next_level_xp = self.system.calculate_xp_for_level(new_level + 1)
            progress = (new_xp / next_level_xp) * 100
            
            embed.add_field(
                name="Progress",
                value=f"Level: {new_level}\nTotal XP: {new_xp:,}\nProgress to Level {new_level + 1}: {progress:.1f}%",
                inline=False
            )

            if role_rewards:
                embed.add_field(
                    name="Rewards Earned",
                    value="\n".join(f"• {guild.get_role(role_id[0]).mention}" for role_id in role_rewards),
                    inline=False
                )

            # Get the level up channel
            async with self.bot.db.cursor() as cursor:
                await cursor.execute("""
                    SELECT level_up_channel_id FROM guild_settings
                    WHERE guild_id = ?
                """, (guild_id,))
                result = await cursor.fetchone()

            channel_id = result[0] if result else None
            channel = guild.get_channel(channel_id) or guild.text_channels[0]
            
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Award XP for messages."""
        if (message.author.bot or
            not message.guild or
            not message.content):
            return

        # Get prefix and check if message starts with it
        prefix = await self.bot.get_prefix(message)
        if isinstance(prefix, list):
            if any(message.content.startswith(p) for p in prefix):
                return
        elif message.content.startswith(prefix):
            return

        # Check if leveling is enabled
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                SELECT leveling_enabled FROM guild_settings
                WHERE guild_id = ?
            """, (message.guild.id,))
            result = await cursor.fetchone()
            
            if not result or not result[0]:
                return

        # Calculate XP (random between 15-25)
        xp_amount = random.randint(15, 25)
        await self.add_xp(message.author.id, message.guild.id, xp_amount, "message")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        """Award XP for reactions (with cooldown)."""
        if user.bot or not reaction.message.guild:
            return

        cooldown_key = (user.id, reaction.message.guild.id)
        if cooldown_key in self.system.reaction_cooldowns:
            return

        self.system.reaction_cooldowns.add(cooldown_key)
        await self.add_xp(user.id, reaction.message.guild.id, 5, "reaction")
        await asyncio.sleep(30)  # 30-second cooldown
        self.system.reaction_cooldowns.discard(cooldown_key)

    @tasks.loop(minutes=5)
    async def voice_xp_task(self):
        """Award XP to users in voice channels."""
        for guild in self.bot.guilds:
            for voice_channel in guild.voice_channels:
                members = [m for m in voice_channel.members 
                         if not m.bot and not m.voice.afk and not m.voice.self_deaf]
                
                if len(members) < 2:  # Need at least 2 people for XP
                    continue

                for member in members:
                    cooldown_key = (member.id, guild.id)
                    current_time = datetime.utcnow()
                    
                    if cooldown_key in self.system.voice_xp_cooldowns:
                        last_time = self.system.voice_xp_cooldowns[cooldown_key]
                        if (current_time - last_time).total_seconds() < 60:
                            continue

                    self.system.voice_xp_cooldowns[cooldown_key] = current_time
                    await self.add_xp(member.id, guild.id, 10, "voice")

    @tasks.loop(minutes=random.randint(30, 60))
    async def drop_spawn_task(self):
        """Spawn XP drops in random channels."""
        for guild in self.bot.guilds:
            if random.random() < 0.3:  # 30% chance to spawn
                channel = random.choice(guild.text_channels)
                
                drop_id = ''.join(random.choices('0123456789ABCDEF', k=8))
                xp_amount = random.randint(100, 500)
                
                embed = discord.Embed(
                    title="📦 XP Drop!",
                    description=f"A mysterious package has appeared!\nBe the first to type `!catch {drop_id}` to claim it!",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Reward", value=f"{xp_amount} XP")
                
                try:
                    message = await channel.send(embed=embed)
                    self.system.active_drops[drop_id] = {
                        'guild_id': guild.id,
                        'channel_id': channel.id,
                        'message_id': message.id,
                        'xp_amount': xp_amount,
                        'expires_at': datetime.utcnow() + timedelta(minutes=5)
                    }
                except discord.HTTPException:
                    continue

    @commands.command()
    async def catch(self, ctx, drop_id: str):
        """Catch an XP drop."""
        if drop_id not in self.system.active_drops:
            await ctx.send("That drop doesn't exist or has already been claimed!")
            return

        drop = self.system.active_drops[drop_id]
        if drop['guild_id'] != ctx.guild.id:
            return
        
        if datetime.utcnow() > drop['expires_at']:
            del self.system.active_drops[drop_id]
            await ctx.send("This drop has expired!")
            return

        await self.add_xp(ctx.author.id, ctx.guild.id, drop['xp_amount'], "drop")
        del self.system.active_drops[drop_id]
        
        await ctx.send(f"🎉 You caught the drop and earned {drop['xp_amount']} XP!")

    @commands.command()
    async def rank(self, ctx, member: discord.Member = None):
        """Show your or another member's rank."""
        member = member or ctx.author

        async with self.bot.db.cursor() as cursor:
            # Get user's XP and level
            await cursor.execute("""
                SELECT xp, level FROM levels
                WHERE user_id = ? AND guild_id = ?
            """, (member.id, ctx.guild.id))
            result = await cursor.fetchone()
            
            if not result:
                await ctx.send(f"{member.display_name} hasn't earned any XP yet!")
                return
                
            xp, level = result

            # Get user's rank
            await cursor.execute("""
                SELECT COUNT(*) FROM levels
                WHERE guild_id = ? AND xp > ?
            """, (ctx.guild.id, xp))
            rank = (await cursor.fetchone())[0] + 1

            # Calculate progress to next level
            current_level_xp = self.system.calculate_xp_for_level(level)
            next_level_xp = self.system.calculate_xp_for_level(level + 1)
            xp_needed = next_level_xp - current_level_xp
            xp_progress = xp - current_level_xp
            progress = (xp_progress / xp_needed) * 100 if xp_needed > 0 else 100

        # Create embed
        embed = discord.Embed(
            title=f"Rank - {member.display_name}",
            color=member.color or discord.Color.blue()
        )

        embed.add_field(
            name="Stats",
            value=f"**Rank:** #{rank}\n**Level:** {level}\n**Total XP:** {xp:,}",
            inline=False
        )

        # Add progress bar
        progress_bar = self.create_progress_bar(progress)
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"{progress_bar} {progress:.1f}%\n{xp_progress:,}/{xp_needed:,} XP",
            inline=False
        )

        # Set thumbnail to user's avatar
        embed.set_thumbnail(url=member.display_avatar.url)

        await ctx.send(embed=embed)

    def create_progress_bar(self, percentage: float, length: int = 20) -> str:
        """Create a text-based progress bar."""
        filled = int((percentage / 100.0) * length)
        return '█' * filled + '░' * (length - filled)

    @commands.command()
    async def leaderboard(self, ctx, page: int = 1):
        """Show the server's XP leaderboard."""
        if page < 1:
            await ctx.send("Page number must be 1 or higher!")
            return

        per_page = 10
        offset = (page - 1) * per_page

        async with self.bot.db.cursor() as cursor:
            # Get total number of ranked users
            await cursor.execute("""
                SELECT COUNT(*) FROM levels
                WHERE guild_id = ? AND xp > 0
            """, (ctx.guild.id,))
            total_users = (await cursor.fetchone())[0]

            if total_users == 0:
                await ctx.send("No one has earned any XP yet!")
                return

            max_pages = math.ceil(total_users / per_page)
            if page > max_pages:
                await ctx.send(f"There are only {max_pages} pages!")
                return

            # Get leaderboard data
            await cursor.execute("""
                SELECT user_id, xp, level
                FROM levels
                WHERE guild_id = ?
                ORDER BY xp DESC
                LIMIT ? OFFSET ?
            """, (ctx.guild.id, per_page, offset))
            leaders = await cursor.fetchall()

        # Create embed
        embed = discord.Embed(
            title=f"🏆 XP Leaderboard - Page {page}/{max_pages}",
            color=discord.Color.gold()
        )

        for i, (user_id, xp, level) in enumerate(leaders, start=offset + 1):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
            embed.add_field(
                name=f"{medal} #{i} - {name}",
                value=f"Level {level} • {xp:,} XP",
                inline=False
            )

        embed.set_footer(text=f"Use {ctx.prefix}leaderboard <page> to see more")
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def levelreward(self, ctx):
        """Manage level rewards."""
        await ctx.send_help(ctx.command)

    @levelreward.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def levelreward_add(self, ctx, level: int, role: discord.Role):
        """Add a role reward for reaching a level."""
        if level < 1:
            await ctx.send("Level must be 1 or higher!")
            return

        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("You can't add a role reward higher than your highest role!")
            return

        async with self.bot.db.cursor() as cursor:
            # Check if role is already a reward
            await cursor.execute("""
                SELECT level_requirement FROM role_rewards
                WHERE guild_id = ? AND role_id = ?
            """, (ctx.guild.id, role.id))
            if await cursor.fetchone():
                await ctx.send("That role is already a level reward!")
                return

            # Add the reward
            await cursor.execute("""
                INSERT INTO role_rewards (guild_id, role_id, level_requirement)
                VALUES (?, ?, ?)
            """, (ctx.guild.id, role.id, level))
            await self.bot.db.commit()

        await ctx.send(f"✅ Added {role.mention} as a reward for reaching level {level}!")

    @levelreward.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def levelreward_remove(self, ctx, role: discord.Role):
        """Remove a role reward."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                DELETE FROM role_rewards
                WHERE guild_id = ? AND role_id = ?
            """, (ctx.guild.id, role.id))
            await self.bot.db.commit()

            if cursor.rowcount > 0:
                await ctx.send(f"✅ Removed {role.mention} from level rewards!")
            else:
                await ctx.send("That role wasn't a level reward!")

    @levelreward.command(name="list")
    async def levelreward_list(self, ctx):
        """List all role rewards."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                SELECT role_id, level_requirement
                FROM role_rewards
                WHERE guild_id = ?
                ORDER BY level_requirement ASC
            """, (ctx.guild.id,))
            rewards = await cursor.fetchall()

        if not rewards:
            await ctx.send("No role rewards set up yet!")
            return

        embed = discord.Embed(
            title="Level Rewards",
            description="Here are all the role rewards for this server:",
            color=discord.Color.blue()
        )

        for role_id, level in rewards:
            role = ctx.guild.get_role(role_id)
            if role:
                embed.add_field(
                    name=f"Level {level}",
                    value=role.mention,
                    inline=False
                )

        await ctx.send(embed=embed)

async def setup(bot):
    # Create necessary tables
    async with bot.db.cursor() as cursor:
        # XP logs table
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS xp_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                xp_amount INTEGER,
                source TEXT,
                timestamp TEXT
            )
        """)
    await bot.db.commit()
    
    await bot.add_cog(Leveling(bot)) 