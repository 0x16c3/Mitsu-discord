import asyncio
import discord
from discord.ext import commands
from discord_slash import SlashCommand

import os, sys
import argparse

os.environ["LOG_LEVEL"] = "WARNING"

from cogs.client import client
from cogs.controller import Controller
from cogs.utils import *
from cogs.api.database import database

from loguru import logger



# create `/tmp`
if not os.path.exists("tmp"):
    os.makedirs("tmp")

# initialize
TOKEN = open("tmp/token.txt", "r").read()

cogs = [
    "cogs.controller",
    "cogs.misc",
    "cogs.eval",
    "cogs.error",
]


slash = SlashCommand(client, sync_commands=True, sync_on_cog_reload=True)


@client.event
async def on_ready():

    # print bot user and discrim on the console
    print("{0.user}".format(client))

    # change the presence
    await client.change_presence(
        status=discord.Status.online,
    )

    # sync commands
    logger.debug("Syncing commands")
    try:
        await slash.sync_all_commands()
        logger.debug("Synced commands")
    except:
        logger.debug("Could not sync commands")

    # setup all feeds
    await client.get_cog("Controller").on_ready()


@client.event
async def on_member_join(member):
    pass


@client.event
async def on_message(message):

    # embed meta
    embed = discord.Embed(color=0xF5F5F5)

    source = "https://github.com/0x16c3/mitsu"
    avatar = client.user.avatar_url

    if message.content == "mitsu":
        embed.set_author(name="Mitsu", url=source, icon_url=avatar)
        embed.set_thumbnail(url=avatar)

        embed.add_field(name="source", value=source, inline=False)
        embed.set_footer(text="光")

        await message.channel.send(embed=embed)

    await client.process_commands(message)


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Process some integers.")

    parser.add_argument(
        "--debug",
        dest="debug",
        type=str2bool,
        nargs="?",
        default=False,
        const=True,
        help="enable debug mode",
    )

    parser.add_argument(
        "--info",
        dest="info",
        type=str2bool,
        nargs="?",
        default=False,
        const=True,
        help="enable info mode",
    )

    args = parser.parse_args()

    os.environ["LOG_LEVEL"] = "WARNING"

    if args.info:
        os.environ["LOG_LEVEL"] = "INFO"
    elif args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>"
        " | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        " | "
        "<level>{level: <8}</level>: <level>{message}</level>"
    )

    logger.remove()
    logger.add(sys.stderr, format=fmt, level=os.environ["LOG_LEVEL"])
    logger.add("logs/log_{time}.log", enqueue=True, rotation="12:00")

    for extension in cogs:
        if args.debug and extension == "cogs.error":
            continue

        try:
            client.load_extension(extension)
        except Exception as error:
            logger.error(f"{extension} could not be activated. [{error}]")

    try:
        client.load_extension("cogs.topgg")
    except:
        pass


async def update_roles(minutes: int):
    while True:

        await asyncio.sleep(minutes * 60)

        logger.debug("Syncing commands")
        await slash.sync_all_commands()
        logger.debug("Synced commands")


try:
    client.loop.create_task(client.get_cog("Controller").process())
    client.loop.create_task(update_roles(minutes=3))
    client.run(TOKEN)
except KeyboardInterrupt:
    print("exit")
