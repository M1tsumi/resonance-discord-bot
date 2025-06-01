import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import re
from collections import defaultdict
import config
import json

def is_dev():
    """Check if the user is a developer."""
    async def predicate(ctx):
        # First check if user is in dev list
        if ctx.author.id in config.DEV_IDS:
            return True
        # If not in dev list, check normal permissions
        return await ctx.command.parent_check(ctx) if ctx.command.parent else True
    return commands.check(predicate)

class Moderation(commands.Cog):
    """🛡️ Server moderation and management commands.
    
    Keep your server safe and organized with these commands:
    • Ban/Kick members
    • Warn system with tracking
    • Message purging
    • Mute system with duration
    • Server prefix management
    """

    def __init__(self, bot):
        self.bot = bot
        self.spam_control = defaultdict(lambda: defaultdict(int))
        self.url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        self.active_mutes = {}

    async def log_action(self, guild, action_type, user, moderator, reason=None, duration=None):
        """Log moderation actions to the designated logging channel."""
        if not guild.id:
            return

        async with self.bot.db.execute(
            "SELECT log_channel_id FROM guild_settings WHERE guild_id = ?",
            (guild.id,)
        ) as cursor:
            result = await cursor.fetchone()

        if not result or not result[0]:
            return

        log_channel = guild.get_channel(result[0])
        if not log_channel:
            return

        embed = discord.Embed(
            title=f"Moderation Action: {action_type}",
            color=config.WARNING_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator} ({moderator.id})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if duration:
            embed.add_field(name="Duration", value=duration, inline=False)

        await log_channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kick a member from the server."""
        if member == ctx.author:
            return await ctx.send("❌ You cannot kick yourself!")
            
        if member.top_role >= ctx.author.top_role and not ctx.author == ctx.guild.owner:
            return await ctx.send("❌ You cannot kick someone with a higher or equal role!")

        reason = reason or "No reason provided"
        full_reason = f"Kicked by {ctx.author} (ID: {ctx.author.id}) - {reason}"

        try:
            # Send DM to user
            embed = discord.Embed(
                title="👢 You have been kicked",
                description=f"You have been kicked from {ctx.guild.name}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason)
            try:
                await member.send(embed=embed)
            except:
                pass  # User might have DMs disabled

            # Kick user
            await member.kick(reason=full_reason)
            
            # Log the kick
            embed = discord.Embed(
                title="👢 Member Kicked",
                description=f"{member.mention} has been kicked",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member} (ID: {member.id})")
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
            # Log to mod-log if exists
            if hasattr(self.bot, 'mod_log'):
                await self.bot.mod_log(ctx.guild, embed)

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to kick that user!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ An error occurred: {e}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Ban a member from the server."""
        if member == ctx.author:
            return await ctx.send("❌ You cannot ban yourself!")
            
        if member.top_role >= ctx.author.top_role and not ctx.author == ctx.guild.owner:
            return await ctx.send("❌ You cannot ban someone with a higher or equal role!")

        reason = reason or "No reason provided"
        full_reason = f"Banned by {ctx.author} (ID: {ctx.author.id}) - {reason}"

        try:
            # Send DM to user
            embed = discord.Embed(
                title="🔨 You have been banned",
                description=f"You have been banned from {ctx.guild.name}",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason)
            try:
                await member.send(embed=embed)
            except:
                pass  # User might have DMs disabled

            # Ban user
            await member.ban(reason=full_reason, delete_message_days=1)
            
            # Log the ban
            embed = discord.Embed(
                title="🔨 Member Banned",
                description=f"{member.mention} has been banned",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member} (ID: {member.id})")
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await ctx.send(embed=embed)
            
            # Log to mod-log if exists
            if hasattr(self.bot, 'mod_log'):
                await self.bot.mod_log(ctx.guild, embed)

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban that user!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ An error occurred: {e}")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        """Warn a member."""
        if member == ctx.author:
            return await ctx.send("❌ You cannot warn yourself!")
            
        if member.top_role >= ctx.author.top_role and not ctx.author == ctx.guild.owner:
            return await ctx.send("❌ You cannot warn someone with a higher or equal role!")

        reason = reason or "No reason provided"

        # Add warning to database
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (ctx.guild.id, member.id, ctx.author.id, reason, datetime.utcnow().isoformat()))
            
            # Get warning count
            await cursor.execute("""
                SELECT COUNT(*) FROM warnings
                WHERE guild_id = ? AND user_id = ?
            """, (ctx.guild.id, member.id))
            warning_count = (await cursor.fetchone())[0]
            
        await self.bot.db.commit()

        # Send warning message
        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"{member.mention} has been warned",
            color=discord.Color.yellow(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{member} (ID: {member.id})")
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Warning Count", value=f"This user now has {warning_count} warning(s)")
        
        await ctx.send(embed=embed)

        # DM the warned user
        try:
            user_embed = discord.Embed(
                title="⚠️ You have been warned",
                description=f"You have received a warning in {ctx.guild.name}",
                color=discord.Color.yellow()
            )
            user_embed.add_field(name="Reason", value=reason)
            user_embed.add_field(name="Warning Count", value=f"You now have {warning_count} warning(s)")
            await member.send(embed=user_embed)
        except:
            pass  # User might have DMs disabled

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member):
        """View warnings for a member."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                SELECT moderator_id, reason, timestamp
                FROM warnings
                WHERE guild_id = ? AND user_id = ?
                ORDER BY timestamp DESC
            """, (ctx.guild.id, member.id))
            warnings = await cursor.fetchall()

        if not warnings:
            return await ctx.send(f"✨ {member} has no warnings!")

        embed = discord.Embed(
            title=f"Warnings for {member}",
            color=discord.Color.yellow()
        )

        for i, (mod_id, reason, timestamp) in enumerate(warnings, 1):
            moderator = ctx.guild.get_member(mod_id) or f"Unknown Moderator ({mod_id})"
            warn_time = datetime.fromisoformat(timestamp)
            
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Moderator:** {moderator}\n"
                      f"**Reason:** {reason}\n"
                      f"**Time:** <t:{int(warn_time.timestamp())}:R>",
                inline=False
            )

        embed.set_footer(text=f"Total Warnings: {len(warnings)}")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(self, ctx, member: discord.Member):
        """Clear all warnings for a member."""
        if member.top_role >= ctx.author.top_role and not ctx.author == ctx.guild.owner:
            return await ctx.send("❌ You cannot clear warnings for someone with a higher or equal role!")

        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                DELETE FROM warnings
                WHERE guild_id = ? AND user_id = ?
            """, (ctx.guild.id, member.id))
        await self.bot.db.commit()

        embed = discord.Embed(
            title="✨ Warnings Cleared",
            description=f"All warnings have been cleared for {member.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int, member: discord.Member = None):
        """Delete a specified number of messages."""
        if amount < 1:
            return await ctx.send("❌ Please specify a positive number of messages to delete!")
        
        if amount > 1000:
            return await ctx.send("❌ Cannot delete more than 1000 messages at once!")

        def check_message(message):
            return member is None or message.author == member

        try:
            # Delete command message
            await ctx.message.delete()
            
            # Delete messages
            deleted = await ctx.channel.purge(
                limit=amount,
                check=check_message,
                before=ctx.message
            )
            
            # Send confirmation
            confirmation = await ctx.send(
                embed=discord.Embed(
                    title="🗑️ Messages Purged",
                    description=f"Deleted {len(deleted)} messages" + (f" from {member.mention}" if member else ""),
                    color=discord.Color.blue()
                )
            )
            
            # Delete confirmation after 5 seconds
            await asyncio.sleep(5)
            await confirmation.delete()
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ An error occurred: {e}")

async def setup(bot):
    # Create necessary tables
    async with bot.db.cursor() as cursor:
        # Warnings table
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                timestamp TEXT
            )
        """)
        
        # Channel locks table
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_locks (
                guild_id INTEGER,
                channel_id INTEGER,
                permissions TEXT,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        
    await bot.db.commit()
    await bot.add_cog(Moderation(bot)) 