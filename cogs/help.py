import discord
from discord.ext import commands
import config
from typing import Dict, List, Optional

# Menu timeout in seconds
MENU_TIMEOUT = 60

class HelpMenu(discord.ui.View):
    """Interactive help menu with category selection."""
    def __init__(self, help_cmd):
        super().__init__(timeout=MENU_TIMEOUT)
        self.help_cmd = help_cmd
        self.add_item(CategoryDropdown(help_cmd))

class CategoryDropdown(discord.ui.Select):
    """Dropdown for selecting help categories."""
    def __init__(self, help_cmd):
        self.help_cmd = help_cmd
        
        # Define available categories
        cats = [
            ("mod", "Moderation", "Server moderation tools", "🛡️"),
            ("lvl", "Leveling", "Experience and ranks", "⭐"),
            ("welcome", "Welcome", "Greeting configuration", "👋"),
            ("fun", "Fun", "Entertainment features", "🎮"),
            ("util", "Utility", "General server tools", "🔧"),
        ]
        
        options = []
        for value, label, desc, emoji in cats:
            options.append(discord.SelectOption(
                value=value,
                label=label, 
                description=desc,
                emoji=emoji
            ))

        super().__init__(
            placeholder="Pick a category...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        embed = await self.help_cmd.make_category_embed(self.values[0])
        await interaction.response.edit_message(embed=embed, view=self.view)

class CustomHelp(commands.HelpCommand):
    """Custom help command implementation with category-based navigation."""
    
    def __init__(self):
        # Set up base attributes
        super().__init__(
            command_attrs={
                'help': 'Shows command help',
                'cooldown': commands.CooldownMapping.from_cooldown(1, 3, commands.BucketType.member)
            }
        )
        self.command_attrs['name'] = 'help'
        self.verify_checks = True

    def _format_cmd_name(self, cmd):
        """Make command name look nice."""
        return cmd.name.replace('_', ' ').title()

    def _format_cmd_usage(self, cmd):
        """Format command usage with proper argument styling."""
        if not cmd.signature:
            return f"`{self.context.clean_prefix}{cmd.name}`"
        
        # Replace ugly brackets with nice unicode ones
        sig = cmd.signature.replace('[', '⟦').replace(']', '⟧')
        sig = sig.replace('<', '⟨').replace('>', '⟩')
        
        return f"`{self.context.clean_prefix}{cmd.name}` {sig}"

    def _get_cmd_desc(self, cmd):
        """Get a short description of the command."""
        if cmd.brief:
            return cmd.brief
        if cmd.help:
            # Just get first line/sentence
            desc = cmd.help.split('.')[0].split('\n')[0]
            return desc + '.'
        return "No description."

    def _get_cmd_perms(self, cmd):
        """Get required permissions for a command."""
        needed_perms = []
        for check in cmd.checks:
            try:
                check_name = check.__qualname__.split('.')[0]
                if check_name == 'has_permissions':
                    perms = check.predicate.permissions
                    for perm, value in perms.items():
                        if value:
                            # Clean up perm name
                            perm = perm.replace('_', ' ').title()
                            needed_perms.append(perm)
            except AttributeError:
                continue
        return needed_perms

    async def send_bot_help(self, mapping):
        """Show main help menu."""
        embed = discord.Embed(
            title="Command Categories",
            description=(
                "Pick a category below to see available commands.\n\n"
                "**Quick Tips:**\n"
                "⟨stuff⟩ = Required\n"
                "⟦stuff⟧ = Optional\n"
            ),
            color=config.INFO_COLOR
        )

        # Show available categories
        cats = {
            "🛡️ Mod": "Ban, kick, warn, and other mod tools",
            "⭐ Leveling": "XP system with ranks and rewards",
            "👋 Welcome": "Custom welcome messages",
            "🎮 Fun": "Games and entertainment",
            "🔧 Utility": "Helpful server tools"
        }
        
        for cat, desc in cats.items():
            cmd = f"{self.context.clean_prefix}help {cat.split()[1].lower()}"
            embed.add_field(
                name=cat,
                value=f"{desc}\nTry `{cmd}`",
                inline=True
            )

        # Add quick stats
        cmd_count = len(self.context.bot.commands)
        embed.set_footer(text=f"{cmd_count} Commands • Use {self.context.clean_prefix}help <command> for details")

        view = HelpMenu(self)
        await self.context.send(embed=embed, view=view)

    async def send_command_help(self, cmd):
        """Show help for a specific command."""
        embed = discord.Embed(
            title=f"Command: {self._format_cmd_name(cmd)}",
            color=config.INFO_COLOR
        )

        # Add description
        embed.description = cmd.help or "No description available."

        # Show how to use it
        embed.add_field(
            name="Usage",
            value=self._format_cmd_usage(cmd),
            inline=False
        )

        # Add examples if we have them
        if hasattr(cmd, 'examples'):
            examples = '\n'.join(f"• `{self.context.clean_prefix}{ex}`" for ex in cmd.examples)
            embed.add_field(name="Examples", value=examples, inline=False)

        # Show required perms
        perms = self._get_cmd_perms(cmd)
        if perms:
            embed.add_field(
                name="Required Permissions",
                value='\n'.join(f"• {perm}" for perm in perms),
                inline=False
            )

        # List aliases
        if cmd.aliases:
            aliases = ', '.join(f"`{alias}`" for alias in cmd.aliases)
            embed.add_field(name="Aliases", value=aliases, inline=False)

        # Show cooldown
        if cmd.cooldown:
            cd = f"{cmd.cooldown.rate} uses per {cmd.cooldown.per:.0f} seconds"
            embed.add_field(name="Cooldown", value=cd, inline=False)

        await self.context.send(embed=embed)

    async def make_category_embed(self, category):
        """Create embed for a command category."""
        # Map short names to full names
        cat_map = {
            'mod': 'Moderation',
            'lvl': 'Leveling',
            'welcome': 'Welcome',
            'fun': 'Fun',
            'util': 'Utility'
        }
        
        # Get the cog
        cog_name = cat_map.get(category, category).title()
        cog = self.context.bot.get_cog(cog_name)
        if not cog:
            return discord.Embed(
                title="Whoops!",
                description="Category not found!",
                color=config.ERROR_COLOR
            )

        # Category styling
        cat_styles = {
            "Moderation": {
                "emoji": "🛡️",
                "desc": "Keep your server safe",
                "color": discord.Color.red()
            },
            "Leveling": {
                "emoji": "⭐",
                "desc": "Level up and earn rewards",
                "color": discord.Color.gold()
            },
            "Welcome": {
                "emoji": "👋",
                "desc": "Greet new members",
                "color": discord.Color.green()
            },
            "Fun": {
                "emoji": "🎮",
                "desc": "Have some fun",
                "color": discord.Color.blue()
            },
            "Utility": {
                "emoji": "🔧",
                "desc": "Useful tools",
                "color": discord.Color.greyple()
            }
        }

        style = cat_styles.get(cog.qualified_name, {
            "emoji": "📁",
            "desc": "Misc commands",
            "color": config.INFO_COLOR
        })

        embed = discord.Embed(
            title=f"{style['emoji']} {cog.qualified_name}",
            description=f"{style['desc']}\nUse `{self.context.clean_prefix}help <command>` for details",
            color=style['color']
        )

        # Sort commands by name
        cmds = sorted(cog.get_commands(), key=lambda x: x.name)
        
        def chunk_commands(cmd_list, chunk_size=5):
            """Split commands into chunks for fields."""
            for i in range(0, len(cmd_list), chunk_size):
                yield cmd_list[i:i + chunk_size]

        # Add commands in chunks
        for i, chunk in enumerate(chunk_commands(cmds)):
            # Format each command
            cmd_text = []
            for cmd in chunk:
                if cmd.hidden:
                    continue
                    
                desc = self._get_cmd_desc(cmd)
                usage = self._format_cmd_usage(cmd)
                
                cmd_text.append(f"**{self._format_cmd_name(cmd)}**")
                cmd_text.append(f"{desc}")
                cmd_text.append(f"{usage}\n")
            
            if cmd_text:  # Only add field if we have visible commands
                embed.add_field(
                    name=f"Commands {i+1}" if i > 0 else "Commands",
                    value='\n'.join(cmd_text),
                    inline=False
                )

        return embed

    async def send_error_message(self, error):
        """Handle command errors."""
        embed = discord.Embed(
            title="Error",
            description=str(error),
            color=config.ERROR_COLOR
        )
        await self.context.send(embed=embed)

    def command_not_found(self, string):
        return f"Command '{string}' not found."

    def subcommand_not_found(self, command, string):
        if isinstance(command, commands.Group) and len(command.all_commands) > 0:
            return f"Subcommand '{string}' for command '{command.qualified_name}' not found."
        return f"Command '{command.qualified_name}' has no subcommands."

class Help(commands.Cog):
    """Help command cog."""
    
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = CustomHelp()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

async def setup(bot):
    await bot.add_cog(Help(bot)) 