import discord
import math
from discord.ext import commands

from .utils import *


class Error(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # if command has local error handler, return
        if hasattr(ctx.command, "on_error"):
            return

        # get the original exception
        error = getattr(error, "original", error)

        command = ctx.command

        if command == None:
            command = "Command"

        if isinstance(error, commands.CommandNotFound):
            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(name="Error", value="Command not found", inline=True)

            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(name="Error", value="Invalid type", inline=False)

            embed.add_field(
                name="Details",
                value=f"`Bad argument`",
                inline=False,
            )

            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.BotMissingPermissions):
            missing = [
                perm.replace("_", " ").replace("guild", "server").title()
                for perm in error.missing_perms
            ]
            if len(missing) > 2:
                fmt = "{}, and {}".format("**, **".join(missing[:-1]), missing[-1])
            else:
                fmt = " and ".join(missing)

            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(name="Error", value="Bot missing permissions", inline=False)

            embed.add_field(name="Details", value=f"`{fmt}`", inline=False)

            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.DisabledCommand):
            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(name="Error", value="Forbidden", inline=False)

            embed.add_field(
                name="Details", value=f"You can't use this command", inline=False
            )

            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(name="Error", value="Too fast", inline=False)

            embed.add_field(
                name="Details",
                value=f"Please retry in `{math.ceil(error.retry_after)}`s",
                inline=False,
            )

            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.MissingPermissions):
            missing = [
                perm.replace("_", " ").replace("guild", "server").title()
                for perm in error.missing_perms
            ]
            if len(missing) > 2:
                fmt = "{}, and {}".format("**, **".join(missing[:-1]), missing[-1])
            else:
                fmt = " and ".join(missing)

            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(name="Error", value="Missing permissions", inline=False)

            embed.add_field(
                name="Details",
                value=f"You don't have the permission: `{fmt}`",
                inline=False,
            )

            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.UserInputError):
            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(
                name="Error", value="Invalid input or argument", inline=True
            )

            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.NoPrivateMessage):
            try:
                embed = discord.Embed(
                    title="{}".format("Something went wrong"),
                    description="Exception in: `{}`".format(command),
                    color=0xF5F5F5,
                )

                embed.add_field(
                    name="Error",
                    value="This command can't be used in private messages",
                    inline=True,
                )

                await ctx.author.send(embed=embed)
            except discord.Forbidden:
                pass
            return

        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="{}".format("Something went wrong"),
                description="Exception in: `{}`".format(command),
                color=0xF5F5F5,
            )

            embed.add_field(
                name="Error",
                value="You don't have permission to use this command",
                inline=True,
            )

            await ctx.author.send(embed=embed)
            return

        # ignore all and print
        # print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)


def setup(client):
    client.add_cog(Error(client))
