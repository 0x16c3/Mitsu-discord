import discord
from discord.ext import commands

# setup intents
intents = discord.Intents().all()

# setup client object
client = commands.Bot(
    command_prefix="mitsu.",
    status=discord.Status.idle,
    activity=discord.Game(name="initializing"),
    intents=intents,
)