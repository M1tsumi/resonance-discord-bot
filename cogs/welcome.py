import discord
from discord.ext import commands
import config
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import os
from datetime import datetime

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self._create_assets_directory()

    def _create_assets_directory(self):
        """Create assets directory if it doesn't exist."""
        if not os.path.exists('assets'):
            os.makedirs('assets')
            
    def cog_unload(self):
        """Cleanup when cog is unloaded."""
        if self.session and not self.session.closed:
            self.bot.loop.create_task(self.session.close())

    async def create_welcome_image(self, member: discord.Member) -> discord.File:
        """Create a custom welcome image for new members."""
        # Download the user's avatar
        avatar_url = member.display_avatar.replace(size=256)
        async with self.session.get(str(avatar_url)) as resp:
            avatar_data = await resp.read()

        # Create base image
        base = Image.new('RGBA', (1000, 300), (47, 49, 54, 255))
        draw = ImageDraw.Draw(base)

        # Load and paste avatar
        avatar = Image.open(io.BytesIO(avatar_data))
        avatar = avatar.resize((200, 200))
        mask = Image.new('L', avatar.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 200, 200), fill=255)
        base.paste(avatar, (50, 50), mask)

        # Add text
        try:
            font = ImageFont.truetype("assets/font.ttf", 60)
            small_font = ImageFont.truetype("assets/font.ttf", 40)
        except:
            # Fallback to default font
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Add welcome text
        draw.text(
            (280, 50),
            f"Welcome to {member.guild.name}!",
            font=font,
            fill=(255, 255, 255)
        )
        draw.text(
            (280, 140),
            f"{member.name}#{member.discriminator}",
            font=small_font,
            fill=(255, 255, 255)
        )
        draw.text(
            (280, 200),
            f"Member #{len(member.guild.members)}",
            font=small_font,
            fill=(255, 255, 255)
        )

        # Save and return
        buffer = io.BytesIO()
        base.save(buffer, 'PNG')
        buffer.seek(0)
        return discord.File(buffer, 'welcome.png')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle new member joins."""
        # Get guild settings
        async with self.bot.db.execute("""
            SELECT welcome_channel_id, welcome_message
            FROM guild_settings
            WHERE guild_id = ?
        """, (member.guild.id,)) as cursor:
            result = await cursor.fetchone()

        if not result:
            return

        channel_id, custom_message = result
        channel = member.guild.get_channel(channel_id) if channel_id else None

        if not channel:
            return

        # Create and send welcome message
        try:
            welcome_image = await self.create_welcome_image(member)
            
            # Format custom message or use default
            message = custom_message or config.DEFAULT_WELCOME_MESSAGE
            message = message.format(
                user=member.mention,
                server=member.guild.name,
                count=len(member.guild.members)
            )

            embed = discord.Embed(
                title="Welcome!",
                description=message,
                color=config.INFO_COLOR,
                timestamp=datetime.utcnow()
            )
            embed.set_image(url="attachment://welcome.png")
            
            await channel.send(
                content=member.mention,
                embed=embed,
                file=welcome_image
            )
        except Exception as e:
            print(f"Error sending welcome message: {e}")

        # Handle auto-roles
        async with self.bot.db.execute("""
            SELECT role_id FROM autorole
            WHERE guild_id = ?
        """, (member.guild.id,)) as cursor:
            autoroles = await cursor.fetchall()

        for role_id, in autoroles:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except discord.HTTPException:
                    continue

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx):
        """Manage welcome system settings."""
        await ctx.send_help(ctx.command)

    @welcome.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def welcome_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the welcome channel."""
        async with self.bot.db.cursor() as cursor:
            if channel:
                await cursor.execute("""
                    UPDATE guild_settings
                    SET welcome_channel_id = ?
                    WHERE guild_id = ?
                """, (channel.id, ctx.guild.id))
                await self.bot.db.commit()
                await ctx.send(f"Welcome channel set to {channel.mention}!")
            else:
                await cursor.execute("""
                    UPDATE guild_settings
                    SET welcome_channel_id = NULL
                    WHERE guild_id = ?
                """, (ctx.guild.id,))
                await self.bot.db.commit()
                await ctx.send("Welcome messages disabled!")

    @welcome.command(name="message")
    @commands.has_permissions(manage_guild=True)
    async def welcome_message(self, ctx, *, message: str = None):
        """Set the welcome message. Use {user} for mention, {server} for server name, {count} for member count."""
        async with self.bot.db.cursor() as cursor:
            if message:
                await cursor.execute("""
                    UPDATE guild_settings
                    SET welcome_message = ?
                    WHERE guild_id = ?
                """, (message, ctx.guild.id))
                await self.bot.db.commit()
                
                # Show preview
                preview = message.format(
                    user=ctx.author.mention,
                    server=ctx.guild.name,
                    count=len(ctx.guild.members)
                )
                await ctx.send(f"Welcome message set! Preview:\n{preview}")
            else:
                await cursor.execute("""
                    UPDATE guild_settings
                    SET welcome_message = NULL
                    WHERE guild_id = ?
                """, (ctx.guild.id,))
                await self.bot.db.commit()
                await ctx.send(f"Reset to default welcome message:\n{config.DEFAULT_WELCOME_MESSAGE}")

    @welcome.command(name="test")
    @commands.has_permissions(manage_guild=True)
    async def welcome_test(self, ctx):
        """Test the welcome message."""
        await self.on_member_join(ctx.author)
        await ctx.send("Sent test welcome message!")

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole(self, ctx):
        """Manage auto-role settings."""
        await ctx.send_help(ctx.command)

    @autorole.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def autorole_add(self, ctx, role: discord.Role):
        """Add a role to be automatically assigned to new members."""
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("You cannot add an auto-role higher than your highest role!")

        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                INSERT OR IGNORE INTO autorole (guild_id, role_id)
                VALUES (?, ?)
            """, (ctx.guild.id, role.id))
        await self.bot.db.commit()

        await ctx.send(f"Added {role.mention} to auto-roles!")

    @autorole.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def autorole_remove(self, ctx, role: discord.Role):
        """Remove a role from auto-roles."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                DELETE FROM autorole
                WHERE guild_id = ? AND role_id = ?
            """, (ctx.guild.id, role.id))
        await self.bot.db.commit()

        await ctx.send(f"Removed {role.mention} from auto-roles!")

    @autorole.command(name="list")
    async def autorole_list(self, ctx):
        """List all auto-roles."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                SELECT role_id FROM autorole
                WHERE guild_id = ?
            """, (ctx.guild.id,))
            roles = await cursor.fetchall()

        if not roles:
            return await ctx.send("No auto-roles set up!")

        embed = discord.Embed(
            title="Auto-Roles",
            description="Roles automatically assigned to new members:",
            color=config.INFO_COLOR
        )

        for role_id, in roles:
            role = ctx.guild.get_role(role_id)
            if role:
                embed.add_field(name=role.name, value=role.mention, inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    # Create necessary tables
    async with bot.db.cursor() as cursor:
        # Auto-role table
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS autorole (
                guild_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        """)
    await bot.db.commit()
    
    await bot.add_cog(Welcome(bot)) 