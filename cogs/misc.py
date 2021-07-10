import discord
from discord.ext import commands

from .utils import *


class Misc(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command(pass_context=True, aliases=["Cogs->load"], hidden=True)
    async def cogs_load(self, ctx, *args):

        """
        Loads specified cogs.
        Can only be ran by ME (0x16c3).

        Args:
            cogs (list(str)): List of cogs to load.
        """

        if str(ctx.author.id) != "346941434202685442":
            return

        for arg in args:
            self.client.load_extension("cogs.{}".format(arg))

        embed = discord.Embed(
            title="Done", description="Loaded:\n`{}`".format("`\n`".join(args))
        )
        await ctx.send(embed=embed)

    @commands.command(pass_context=True, aliases=["Cogs->unload"], hidden=True)
    async def cogs_unload(self, ctx, *args):

        """
        Unloads specified cogs.
        Can only be ran by ME (0x16c3).

        Args:
            cogs (list(str)): List of cogs to unload.
        """

        if str(ctx.author.id) != "346941434202685442":
            return

        for arg in args:
            self.client.unload_extension("cogs.{}".format(arg))

        embed = discord.Embed(
            title="Done", description="Unloaded:\n`{}`".format("`\n`".join(args))
        )
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Misc(client))
