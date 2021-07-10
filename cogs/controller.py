# discord imports
import discord
from discord.ext import commands
import asyncio

# for slash commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.model import SlashCommandOptionType

# utilities
from .utils import *
from .api.database import database
from .api.types import CUser, CAnime, CManga, CListActivity


class Feed:

    TYPE = {"ANIME": 0, "MANGA": 1}

    def get_type(self, i: any):
        return list(self.TYPE.keys())[list(self.TYPE.values()).index(i)]

    def __init__(self, username: str, feed: int) -> None:
        self.username = username
        self.feed = feed

        self.function = None
        self.arguments = None
        self.type = None

        if self.feed == self.TYPE["ANIME"]:
            self.type = CListActivity
            self.function = anilist.get_activity
            self.arguments = {
                "id": self.username,
                "content_type": "anime",
            }

        self.entries = []
        self.entries_processed = []
        self._init = False

    async def retrieve(self) -> Dict[List[CListActivity], List[CListActivity]]:
        try:
            ret = await self.function(**self.arguments)

            res = []
            for item in ret:
                obj = self.type.create(item, self.username)
                res.append(obj)

        except Exception as e:
            logger.print("Error on {}: {}".format(self.username, e))
            return []

        return res[:15], res

    async def update(self, feed: list, feed_full: list) -> None:

        self.entries_full = feed_full

        if not self._init:
            for item in feed_full:
                self.entries_processed.append(item)

            self._init = True

            logger.info("Initialized " + str(self))
            logger.debug(
                "\n  List:\n   "
                + "\n   ".join(str(x.id) for x in self.entries_processed)
            )
            return

        for item in feed:
            if item.id in (i.id for i in self.entries_processed):
                continue

            logger.info("Added " + str(item.id))
            self.entries.append(item)

    async def move_item(self, item, func=None, **kwargs) -> bool:

        processed = False

        if item not in self.entries_processed:

            if func:
                try:
                    await func(item=item, **kwargs)
                except Exception as e:
                    print(e)

            if self.type == CListActivity:

                # replace in list if it exists
                if any(
                    (
                        x
                        for x in self.entries_processed
                        if item.media.title.native == x.media.title.native
                    )
                ):
                    obj = next(
                        (
                            x
                            for x in self.entries_processed
                            if item.media.title.native == x.media.title.native
                        ),
                        None,
                    )
                    idx = self.entries_processed.index(obj)

                    self.entries_processed[idx] = item

                else:
                    # append if doesn't exist
                    self.entries_processed.append(item)
            else:
                # not complete
                self.entries_processed.insert(0, item)
                self.entries_processed = self.entries_processed

            self.entries.remove(item)

            processed = True

        return processed

    async def process_entries(self, func, **kwargs) -> None:

        logger.debug(str(self) + ".entries:" + str(len(self.entries)))
        logger.debug(
            str(self) + ".entries_processed:" + str(len(self.entries_processed))
        )

        processed = False

        for item in self.entries[:]:

            moved = await self.move_item(item, func, **kwargs)

            if moved:
                processed = True

        if processed and len(self.entries_processed) > int(config["MEMORY_LIMIT"]):
            self.entries_processed = []
            self.entries = []
            self._init = False
            logger.info("Reset " + str(self) + " - exceeded entry limit.")
            return

        return


class AnimeFeed:
    def __init__(
        self, username: str, channel: discord.TextChannel, profile: CUser
    ) -> None:
        self.username = username
        self.channel = channel
        self.profile = profile

        self.feed_anime = Feed(username, Feed.TYPE["ANIME"])

        self.loop = None

    @staticmethod
    async def create(username: str, channel: discord.TextChannel) -> "AnimeFeed":

        try:
            profile = await anilist.get_user(name=username)
            profile = CUser.create(profile)
        except:
            return None

        return AnimeFeed(username, channel, profile)

    async def get_feed(
        self, feed: Feed
    ) -> Dict[List[CListActivity], List[CListActivity]]:

        items, items_full = await feed.retrieve()

        if len(items) == 0:
            return []

        await feed.update(items, items_full)
        return items, items_full

    def __repr__(self):
        return "<AnimeFeed: {}:{}>".format(self.username, str(self.channel.id))

    def __eq__(self, o: "AnimeFeed"):
        return "<AnimeFeed: {}:{}>".format(self.username, str(self.channel.id)) == str(
            o
        )

    def JSON(self):
        return json.loads(
            json.dumps({"username": self.username, "channel": str(self.channel.id)})
        )


class Controller(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.feeds: List[AnimeFeed] = []

    async def on_ready(self):
        items = await database.feed_get()

        logger.info(f"Loading {len(items)} feeds that exist in the database.")
        for item in items:
            channel = self.client.get_channel(int(item["channel"]))

            if not channel:
                logger.debug(f"Could not load <{item['username']}:{item['channel']}>")
                await database.feed_remove([item])
                continue

            user: AnimeFeed = await AnimeFeed.create(item["username"], channel)
            self.feeds.append(user)

        logger.info(f"Loaded {len(self.feeds)}.")

    async def process(self):

        while True:
            for user in self.feeds:
                user: AnimeFeed

                await user.get_feed(user.feed_anime)
                await user.feed_anime.process_entries(
                    user.feed_anime.type.send_embed,
                    channel=user.channel,
                    anilist=anilist,
                )

            await asyncio.sleep(
                int(config["INTERVAL"]) if self.client.is_ready() else 1
            )

    async def get_anime(self, query: str) -> CAnime:
        pass

    @cog_ext.cog_slash(
        name="setup",
        description="Setup RSS feed in current channel.",
        guild_ids=get_all_guild_ids(),
        permissions=get_all_permissions(),
        options=[
            create_option(
                name="username",
                description="MyAnimeList username.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
        ],
    )
    async def _setup(self, ctx: SlashContext, username: str):

        if not ctx.author.permissions_in(ctx.channel).manage_webhooks:
            await ctx.send(
                "You don't have the permission to use this command.", hidden=True
            )
            return

        await ctx.defer(hidden=True)

        user: AnimeFeed = await AnimeFeed.create(username, ctx.channel)

        if not user:
            embed = discord.Embed(
                title="Could not start tracking!",
                description=(
                    "There has been an error fetching this profile.\n"
                    "Please double-check the username or try again later."
                ),
                color=color_errr,
            )
            await ctx.send(" ឵឵", embed=embed, hidden=True)
            return

        if user not in self.feeds:
            self.feeds.append(user)
            await database.feed_insert([user.JSON()])
            embed = discord.Embed(
                title="Done!",
                description=f"This channel will now track the anime list of {user.username}",
                color=color_done,
            )
        else:
            embed = discord.Embed(
                title="Could not start tracking!",
                description=f"This channel is already tracking {user.username}!",
                color=color_warn,
            )

        await user.get_feed(user.feed_anime)
        await user.feed_anime.process_entries(
            user.feed_anime.type.send_embed,
            channel=user.channel,
            profile=user.profile,
        )

        await ctx.send(" ឵឵", embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="remove",
        description="Remove active RSS feed in current channel.",
        guild_ids=get_all_guild_ids(),
        permissions=get_all_permissions(),
        options=[
            create_option(
                name="username",
                description="MyAnimeList username.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
        ],
    )
    async def _remove(self, ctx: SlashContext, username: str):

        if not ctx.author.permissions_in(ctx.channel).manage_webhooks:
            await ctx.send(
                "You don't have the permission to use this command.", hidden=True
            )
            return

        await ctx.defer(hidden=True)

        if any(
            user
            for user in self.feeds
            if user.username == username and user.channel == ctx.channel
        ):
            user = next(
                user
                for user in self.feeds
                if user.username == username and user.channel == ctx.channel
            )
            self.feeds.remove(user)
            await database.feed_remove([user.JSON()])
            embed = discord.Embed(
                title="Done!",
                description=f"This channel will now stop tracking the anime list of {user.username}",
                color=color_done,
            )
            del user
        else:
            embed = discord.Embed(
                title="Could not stop tracking!",
                description=f"This channel is not tracking {username}!",
                color=color_warn,
            )

        await ctx.send(" ឵឵", embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="active",
        description="See active feeds.",
        guild_ids=get_all_guild_ids(),
        permissions=get_all_permissions(),
        options=[
            create_option(
                name="scope",
                description="The scope for active feeds.",
                option_type=SlashCommandOptionType.INTEGER,
                required=True,
                choices=[
                    create_choice(name="This channel", value=0),
                    create_choice(name="Whole server", value=1),
                ],
            ),
        ],
    )
    async def _get_active(self, ctx: SlashContext, scope: int):

        SCOPE = {"This channel": 0, "Whole server": 1}

        items = []

        if scope == SCOPE["This channel"]:
            items = (
                feed
                for feed in self.feeds
                if feed and feed.channel and feed.channel == ctx.channel
            )
        elif scope == SCOPE["Whole server"]:
            items = (
                feed
                for feed in self.feeds
                if feed and feed.channel and feed.channel.guild == ctx.guild
            )

        def format_str(feed: AnimeFeed) -> str:
            if scope == SCOPE["This channel"]:
                return feed.username
            elif scope == SCOPE["Whole server"]:
                return feed.username + " -> #" + feed.channel.name

        await ctx.send(
            "```\n" + "\n".join((format_str(feed) for feed in items)) + "```",
            hidden=True,
        )

    @cog_ext.cog_slash(
        name="profile",
        description="Get user profile.",
        guild_ids=get_all_guild_ids(),
        options=[
            create_option(
                name="username",
                description="MyAnimeList username.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
            create_option(
                name="send-message",
                description="Send a public message.",
                option_type=SlashCommandOptionType.BOOLEAN,
                required=False,
            ),
        ],
    )
    async def _get_profile(
        self, ctx: SlashContext, username: str, send_message: bool = False
    ):
        send_message = not send_message
        await ctx.defer(hidden=send_message)

        try:
            profile = await anilist.get_user(name=username)
            profile = CUser.create(profile)
        except Exception as ex:
            embed = discord.Embed(
                title=f"There has been an error getting the profile `{username}`!",
                description=ex,
                color=color_errr,
            )
            await ctx.send(" ឵឵", embed=embed, hidden=True)
            return

        embed = await profile.send_embed()
        await ctx.send(" ឵឵", embed=embed, hidden=send_message)


def setup(client):
    client.add_cog(Controller(client))
