import discord
from discord.ext import commands
import config
import random
import aiohttp
import asyncio
from datetime import datetime, timedelta
import json

class Fun(commands.Cog):
    """Fun and entertainment commands."""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.eight_ball_responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.",
            "Yes - definitely.", "You may rely on it.", "As I see it, yes.",
            "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
            "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful."
        ]

    def cog_unload(self):
        if self.session and not self.session.closed:
            self.bot.loop.create_task(self.session.close())

    @commands.command(name="8ball")
    async def eight_ball(self, ctx, *, question: str):
        """Ask the magic 8-ball a question."""
        response = random.choice(self.eight_ball_responses)
        embed = discord.Embed(
            title="🎱 Magic 8-Ball",
            color=config.INFO_COLOR
        )
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=response, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def roll(self, ctx, dice: str = "1d6"):
        """Roll dice in NdN format."""
        try:
            rolls, limit = map(int, dice.split('d'))
        except Exception:
            return await ctx.send("Format has to be in NdN!")

        if rolls > 25:
            return await ctx.send("Too many dice! Maximum is 25")
        if limit > 100:
            return await ctx.send("Dice too big! Maximum is 100")

        results = [random.randint(1, limit) for _ in range(rolls)]
        total = sum(results)

        embed = discord.Embed(
            title="🎲 Dice Roll",
            color=config.INFO_COLOR
        )
        embed.add_field(name="Rolls", value=", ".join(map(str, results)), inline=False)
        embed.add_field(name="Total", value=str(total), inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def coinflip(self, ctx):
        """Flip a coin."""
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"The coin landed on: **{result}**",
            color=config.INFO_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def rps(self, ctx, choice: str):
        """Play Rock, Paper, Scissors with the bot."""
        choice = choice.lower()
        if choice not in ["rock", "paper", "scissors"]:
            return await ctx.send("Please choose rock, paper, or scissors!")

        bot_choice = random.choice(["rock", "paper", "scissors"])
        
        # Determine winner
        if choice == bot_choice:
            result = "It's a tie!"
            color = config.INFO_COLOR
        elif (
            (choice == "rock" and bot_choice == "scissors") or
            (choice == "paper" and bot_choice == "rock") or
            (choice == "scissors" and bot_choice == "paper")
        ):
            result = "You win!"
            color = config.SUCCESS_COLOR
        else:
            result = "I win!"
            color = config.ERROR_COLOR

        # Create embed
        embed = discord.Embed(
            title="✂️ Rock, Paper, Scissors",
            color=color
        )
        embed.add_field(name="Your Choice", value=choice.title())
        embed.add_field(name="My Choice", value=bot_choice.title())
        embed.add_field(name="Result", value=result, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def meme(self, ctx):
        """Get a random meme from Reddit."""
        async with self.session.get("https://meme-api.com/gimme") as response:
            if response.status != 200:
                return await ctx.send("Failed to get meme!")
            
            data = await response.json()
            
            embed = discord.Embed(
                title=data["title"],
                url=data["postLink"],
                color=config.INFO_COLOR
            )
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"👍 {data['ups']} | From r/{data['subreddit']}")
            await ctx.send(embed=embed)

    @commands.command()
    async def poll(self, ctx, question: str, *options):
        """Create a poll with up to 10 options."""
        if len(options) < 2:
            return await ctx.send("Please provide at least 2 options!")
        if len(options) > 10:
            return await ctx.send("Maximum 10 options allowed!")

        # Create embed
        embed = discord.Embed(
            title="📊 Poll",
            description=question,
            color=config.INFO_COLOR,
            timestamp=datetime.utcnow()
        )
        
        # Add options
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, option in enumerate(options):
            embed.add_field(
                name=f"Option {i+1}",
                value=f"{number_emojis[i]} {option}",
                inline=False
            )

        embed.set_footer(text=f"Started by {ctx.author}")
        
        # Send poll and add reactions
        poll_message = await ctx.send(embed=embed)
        for i in range(len(options)):
            await poll_message.add_reaction(number_emojis[i])

    @commands.command()
    async def choose(self, ctx, *choices: str):
        """Choose between multiple options."""
        if len(choices) < 2:
            return await ctx.send("Please provide at least 2 choices!")
        
        embed = discord.Embed(
            title="🤔 Choice",
            description=f"I choose: **{random.choice(choices)}**",
            color=config.INFO_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def reverse(self, ctx, *, text: str):
        """Reverse the given text."""
        await ctx.send(f"🔄 {text[::-1]}")

    @commands.command()
    async def emojify(self, ctx, *, text: str):
        """Convert text to regional indicator emojis."""
        regional_indicators = {
            'a': '🇦', 'b': '🇧', 'c': '🇨', 'd': '🇩', 'e': '🇪',
            'f': '🇫', 'g': '🇬', 'h': '🇭', 'i': '🇮', 'j': '🇯',
            'k': '🇰', 'l': '🇱', 'm': '🇲', 'n': '🇳', 'o': '🇴',
            'p': '🇵', 'q': '🇶', 'r': '🇷', 's': '🇸', 't': '🇹',
            'u': '🇺', 'v': '🇻', 'w': '🇼', 'x': '🇽', 'y': '🇾',
            'z': '🇿'
        }
        
        emojified = ' '.join(regional_indicators.get(c.lower(), c) for c in text)
        await ctx.send(emojified)

    @commands.command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def joke(self, ctx):
        """Get a random joke."""
        async with self.session.get("https://v2.jokeapi.dev/joke/Any?safe-mode") as response:
            if response.status != 200:
                return await ctx.send("Failed to get joke!")
            
            data = await response.json()
            
            embed = discord.Embed(
                title="😄 Random Joke",
                color=config.INFO_COLOR
            )
            
            if data["type"] == "single":
                embed.description = data["joke"]
            else:
                embed.add_field(name="Setup", value=data["setup"], inline=False)
                embed.add_field(name="Punchline", value=data["delivery"], inline=False)
                
            await ctx.send(embed=embed)

    @commands.command()
    async def fact(self, ctx):
        """Get a random fact."""
        async with self.session.get("https://uselessfacts.jsph.pl/random.json?language=en") as response:
            if response.status != 200:
                return await ctx.send("Failed to get fact!")
            
            data = await response.json()
            
            embed = discord.Embed(
                title="📚 Random Fact",
                description=data["text"],
                color=config.INFO_COLOR
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Fun(bot)) 
