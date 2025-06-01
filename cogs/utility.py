import discord
from discord.ext import commands
import config
from datetime import datetime
import platform
import psutil
import os
from typing import Optional, Union
import time

class Utility(commands.Cog):
    """Utility and information commands."""

    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    def format_dt(self, dt: datetime) -> str:
        """Format a datetime object to a readable string."""
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    @commands.command()
    async def ping(self, ctx):
        """Get the bot's latency."""
        start = time.perf_counter()
        message = await ctx.send("Pinging...")
        end = time.perf_counter()
        
        duration = (end - start) * 1000
        websocket_latency = self.bot.latency * 1000
        
        embed = discord.Embed(
            title="🏓 Pong!",
            color=config.INFO_COLOR
        )
        embed.add_field(name="Bot Latency", value=f"{duration:.2f}ms")
        embed.add_field(name="Websocket Latency", value=f"{websocket_latency:.2f}ms")
        
        await message.edit(content=None, embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        """Get information about the server."""
        guild = ctx.guild
        
        # Get channel counts
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        total_channels = text_channels + voice_channels
        
        # Get member counts
        total_members = guild.member_count
        online_members = len([m for m in guild.members if m.status != discord.Status.offline])
        bot_count = len([m for m in guild.members if m.bot])
        
        # Create embed
        embed = discord.Embed(
            title=f"Server Information - {guild.name}",
            color=config.INFO_COLOR
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        # General information
        embed.add_field(
            name="General",
            value=f"**Owner:** {guild.owner.mention}\n"
                  f"**Created:** {discord.utils.format_dt(guild.created_at, 'R')}\n"
                  f"**Verification Level:** {str(guild.verification_level).title()}\n"
                  f"**Server ID:** {guild.id}",
            inline=False
        )
        
        # Member information
        embed.add_field(
            name="Members",
            value=f"**Total:** {total_members:,}\n"
                  f"**Online:** {online_members:,}\n"
                  f"**Humans:** {total_members - bot_count:,}\n"
                  f"**Bots:** {bot_count:,}",
            inline=True
        )
        
        # Channel information
        embed.add_field(
            name="Channels",
            value=f"**Total:** {total_channels:,}\n"
                  f"**Text:** {text_channels:,}\n"
                  f"**Voice:** {voice_channels:,}\n"
                  f"**Categories:** {categories:,}",
            inline=True
        )
        
        # Emoji information
        emoji_stats = f"**Regular:** {len([e for e in guild.emojis if not e.animated])}\n" \
                     f"**Animated:** {len([e for e in guild.emojis if e.animated])}\n" \
                     f"**Total:** {len(guild.emojis)}"
        embed.add_field(name="Emojis", value=emoji_stats, inline=True)
        
        # Server features
        if guild.features:
            features_str = "\n".join(f"✓ {feature.replace('_', ' ').title()}" for feature in guild.features)
            if len(features_str) > 1024:  # Discord embed field value limit
                features_str = features_str[:1021] + "..."
            embed.add_field(
                name="Features",
                value=features_str,
                inline=False
            )
            
        # Server boost status
        embed.add_field(
            name="Boost Status",
            value=f"**Level:** {guild.premium_tier}\n"
                  f"**Boosts:** {guild.premium_subscription_count or 0}\n"
                  f"**Boosters:** {len(guild.premium_subscribers) if guild.premium_subscribers else 0}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Get information about a user."""
        member = member or ctx.author
        
        roles = [role.mention for role in member.roles[1:]]  # All roles except @everyone
        
        embed = discord.Embed(
            title=f"User Information - {member}",
            color=member.color or config.INFO_COLOR
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # General information
        embed.add_field(
            name="General",
            value=f"**Username:** {member}\n"
                  f"**ID:** {member.id}\n"
                  f"**Nickname:** {member.nick or 'None'}\n"
                  f"**Bot:** {'Yes' if member.bot else 'No'}",
            inline=False
        )
        
        # Time information
        embed.add_field(
            name="Time Information",
            value=f"**Account Created:** {discord.utils.format_dt(member.created_at, 'R')}\n"
                  f"**Joined Server:** {discord.utils.format_dt(member.joined_at, 'R')}",
            inline=False
        )
        
        # Roles
        if roles:
            embed.add_field(
                name=f"Roles [{len(roles)}]",
                value=" ".join(roles) if len(roles) <= 10 else " ".join(roles[:10]) + f" ... and {len(roles)-10} more",
                inline=False
            )
            
        # Permissions
        key_permissions = []
        if member.guild_permissions.administrator:
            key_permissions.append("Administrator")
        if member.guild_permissions.manage_guild:
            key_permissions.append("Manage Server")
        if member.guild_permissions.manage_roles:
            key_permissions.append("Manage Roles")
        if member.guild_permissions.manage_channels:
            key_permissions.append("Manage Channels")
        if member.guild_permissions.manage_messages:
            key_permissions.append("Manage Messages")
        if member.guild_permissions.kick_members:
            key_permissions.append("Kick Members")
        if member.guild_permissions.ban_members:
            key_permissions.append("Ban Members")
            
        if key_permissions:
            embed.add_field(
                name="Key Permissions",
                value="\n".join(f"✓ {perm}" for perm in key_permissions),
                inline=False
            )
            
        await ctx.send(embed=embed)

    @commands.command()
    async def avatar(self, ctx, member: discord.Member = None):
        """Get a user's avatar."""
        member = member or ctx.author
        
        embed = discord.Embed(
            title=f"Avatar - {member}",
            color=member.color or config.INFO_COLOR
        )
        embed.set_image(url=member.display_avatar.url)
        
        await ctx.send(embed=embed)

    @commands.command()
    async def roleinfo(self, ctx, role: discord.Role):
        """Get information about a role."""
        embed = discord.Embed(
            title=f"Role Information - {role.name}",
            color=role.color or config.INFO_COLOR
        )
        
        # General information
        embed.add_field(
            name="General",
            value=f"**Name:** {role.name}\n"
                  f"**ID:** {role.id}\n"
                  f"**Color:** {str(role.color)}\n"
                  f"**Position:** {role.position}\n"
                  f"**Created:** {discord.utils.format_dt(role.created_at, 'R')}\n"
                  f"**Mentionable:** {'Yes' if role.mentionable else 'No'}\n"
                  f"**Hoisted:** {'Yes' if role.hoist else 'No'}\n"
                  f"**Managed:** {'Yes' if role.managed else 'No'}",
            inline=False
        )
        
        # Members with this role
        members_with_role = len(role.members)
        embed.add_field(
            name="Members",
            value=f"{members_with_role:,} member{'s' if members_with_role != 1 else ''} have this role",
            inline=False
        )
        
        # Key permissions
        key_permissions = []
        if role.permissions.administrator:
            key_permissions.append("Administrator")
        if role.permissions.manage_guild:
            key_permissions.append("Manage Server")
        if role.permissions.manage_roles:
            key_permissions.append("Manage Roles")
        if role.permissions.manage_channels:
            key_permissions.append("Manage Channels")
        if role.permissions.manage_messages:
            key_permissions.append("Manage Messages")
        if role.permissions.kick_members:
            key_permissions.append("Kick Members")
        if role.permissions.ban_members:
            key_permissions.append("Ban Members")
            
        if key_permissions:
            embed.add_field(
                name="Key Permissions",
                value="\n".join(f"✓ {perm}" for perm in key_permissions),
                inline=False
            )
            
        await ctx.send(embed=embed)

    @commands.command()
    async def botinfo(self, ctx):
        """Get information about the bot."""
        embed = discord.Embed(
            title="Bot Information",
            color=config.INFO_COLOR
        )
        
        # Calculate uptime
        uptime = datetime.utcnow() - self.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Get system info
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
        
        # Bot stats
        total_members = sum(guild.member_count for guild in self.bot.guilds)
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)
        
        embed.add_field(
            name="Bot Stats",
            value=f"**Guilds:** {len(self.bot.guilds):,}\n"
                  f"**Users:** {total_members:,}\n"
                  f"**Channels:** {total_channels:,}\n"
                  f"**Commands:** {len(self.bot.commands):,}",
            inline=True
        )
        
        embed.add_field(
            name="System Info",
            value=f"**Python:** {platform.python_version()}\n"
                  f"**Discord.py:** {discord.__version__}\n"
                  f"**Memory:** {memory_usage:.1f} MB\n"
                  f"**OS:** {platform.system()} {platform.release()}",
            inline=True
        )
        
        embed.add_field(
            name="Uptime",
            value=f"{days}d {hours}h {minutes}m {seconds}s",
            inline=True
        )
        
        await ctx.send(embed=embed)

    @commands.command()
    async def channelinfo(self, ctx, channel: Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel] = None):
        """Get information about a channel."""
        channel = channel or ctx.channel
        
        embed = discord.Embed(
            title=f"Channel Information - #{channel.name}",
            color=config.INFO_COLOR
        )
        
        # General information
        channel_type = str(channel.type).replace('_', ' ').title()
        
        embed.add_field(
            name="General",
            value=f"**Name:** {channel.name}\n"
                  f"**ID:** {channel.id}\n"
                  f"**Type:** {channel_type}\n"
                  f"**Created:** {discord.utils.format_dt(channel.created_at, 'R')}",
            inline=False
        )
        
        # Category
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            embed.add_field(
                name="Category",
                value=channel.category.name if channel.category else "None",
                inline=False
            )
        
        # Channel-specific information
        if isinstance(channel, discord.TextChannel):
            embed.add_field(
                name="Text Channel Info",
                value=f"**Topic:** {channel.topic or 'None'}\n"
                      f"**NSFW:** {'Yes' if channel.is_nsfw() else 'No'}\n"
                      f"**Slowmode:** {channel.slowmode_delay}s",
                inline=False
            )
        elif isinstance(channel, discord.VoiceChannel):
            embed.add_field(
                name="Voice Channel Info",
                value=f"**Bitrate:** {channel.bitrate//1000}kbps\n"
                      f"**User Limit:** {channel.user_limit or 'Unlimited'}\n"
                      f"**Connected Users:** {len(channel.members)}",
                inline=False
            )
        elif isinstance(channel, discord.CategoryChannel):
            embed.add_field(
                name="Category Info",
                value=f"**Channels:** {len(channel.channels)}\n"
                      f"**Text Channels:** {len(channel.text_channels)}\n"
                      f"**Voice Channels:** {len(channel.voice_channels)}",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot)) 