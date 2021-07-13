# discord imports
import discord
from discord.ext import commands
import asyncio

# for slash commands
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_components import (
    create_select,
    create_select_option,
    create_actionrow,
    wait_for_component,
)

# utilities
from .utils import *
from .api.database import database
from .api.types import CUser, CAnime, CManga, CListActivity, CTextActivity
from typing import Union


class Feed:

    TYPE = {"ANIME": 0, "MANGA": 1, "TEXT": 2}

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
        if self.feed == self.TYPE["MANGA"]:
            self.type = CListActivity
            self.function = anilist.get_activity
            self.arguments = {
                "id": self.username,
                "content_type": "manga",
            }
        if self.feed == self.TYPE["TEXT"]:
            self.type = CTextActivity
            self.function = anilist.get_activity
            self.arguments = {
                "id": self.username,
                "content_type": "text",
            }

        self.entries = []
        self.entries_processed = []
        self._init = False

    async def retrieve(
        self,
    ) -> Dict[
        List[Union[CListActivity, CTextActivity]],
        List[Union[CListActivity, CTextActivity]],
    ]:
        try:
            ret = await self.function(**self.arguments)

            if not ret:
                return [], []

            res = []
            for item in ret:
                obj = self.type.create(item, self.username)
                res.append(obj)

        except Exception as e:
            logger.print("Error on {}: {}".format(self.username, e))
            return [], []

        return res[:15], res

    async def update(self, feed: list, feed_full: list) -> None:

        if not self._init:
            for item in feed:
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
            if self.type == CListActivity:
                if item.media.id in (i.media.id for i in self.entries):
                    continue

            self.entries.insert(0, item)
            logger.info("Added " + str(item.id))

    async def move_item(self, item, func=None, **kwargs) -> bool:

        processed = False

        if item not in self.entries_processed:

            if func:
                try:
                    await func(item=item, **kwargs)
                except Exception as e:
                    logger.print(
                        "Error running function on entry {}: {}".format(item.id, e)
                    )

            if self.type == CListActivity:
                self.entries_processed.insert(0, item)
            elif self.type == CTextActivity:
                self.entries_processed.insert(0, item)

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

            items, items_full = await self.retrieve()
            if len(items) == 0:
                logger.info("Could not reset " + str(self) + " - FALLBACK (NEXT TICK)")
                return []

            await self.update(items, items_full)

            logger.info("Reset " + str(self) + " - exceeded entry limit.")
            return

        return


class Activity:
    def __init__(
        self,
        username: str,
        channel: discord.TextChannel,
        profile: CUser,
        type: Union[str, int] = "ANIME",
    ) -> None:
        self.username = username
        self.channel = channel
        self.profile = profile

        self.type = Feed.TYPE[type] if isinstance(type, str) else type
        self.feed = Feed(username, self.type)

        self.loop = None

    @staticmethod
    async def create(
        username: str, channel: discord.TextChannel, type: Union[int, str] = "ANIME"
    ) -> "Activity":

        try:
            profile = await anilist.get_user(name=username)
            profile = CUser.create(profile)
        except:
            return None

        return Activity(username, channel, profile, type)

    async def get_feed(
        self, feed: Feed
    ) -> Dict[
        List[Union[CListActivity, CTextActivity]],
        List[Union[CListActivity, CTextActivity]],
    ]:

        items, items_full = await feed.retrieve()

        await feed.update(items, items_full)
        return items, items_full

    def __repr__(self):
        return "<Activity: {}:{}>".format(self.username, str(self.channel.id))

    def __eq__(self, o: "Activity"):
        return "<Activity: {}:{}>".format(self.username, str(self.channel.id)) == str(o)

    def JSON(self):
        return json.loads(
            json.dumps(
                {
                    "username": self.username,
                    "channel": str(self.channel.id),
                    "type": str(self.type),
                }
            )
        )


class Controller(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.feeds: List[Activity] = []

    async def on_ready(self):
        items = await database.feed_get()

        logger.info(f"Loading {len(items)} feeds that exist in the database.")
        for item in items:
            channel = self.client.get_channel(int(item["channel"]))

            if not channel:
                logger.debug(
                    f"Could not load <{item['username']}:{item['channel']}:{item['type']}>"
                )
                await database.feed_remove([item])
                continue

            user: Activity = await Activity.create(
                item["username"], channel, int(item["type"])
            )
            self.feeds.append(user)

        for user in self.feeds:
            user: Activity

            await user.get_feed(user.feed)
            await user.feed.process_entries(
                user.feed.type.send_embed,
                channel=user.channel,
                anilist=anilist,
            )

        logger.info(f"Loaded {len(self.feeds)}.")

    async def process(self):

        while True:

            await asyncio.sleep(int(config["INTERVAL"]))

            for user in self.feeds:
                user: Activity

                await user.get_feed(user.feed)
                await user.feed.process_entries(
                    user.feed.type.send_embed,
                    channel=user.channel,
                    anilist=anilist,
                )

    @cog_ext.cog_slash(
        name="search",
        description="Search for media.",
        guild_ids=get_debug_guild_id(),
        options=[
            create_option(
                name="media",
                description="Media type to search.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
                choices=[
                    create_choice(name="Anime", value="anime"),
                    create_choice(name="Manga", value="manga"),
                ],
            ),
            create_option(
                name="query",
                description="Search query.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
        ],
    )
    async def _search(self, ctx: SlashContext, media: str, query: str) -> CAnime:
        results: List[Union[CAnime, CManga]] = await anilist.search(
            query, content_type=media, page=1, limit=5
        )
        select = create_select(
            options=[
                create_select_option(
                    label=(
                        i.title.romaji
                        if len(i.title.romaji) <= 25
                        else i.title.romaji[:22] + "..."
                    ),
                    description=(
                        i.title.english
                        if len(i.title.english) <= 50
                        else i.title.english[:47] + "..."
                    ),
                    value=str(i.id),
                )
                for i in results
            ],
            placeholder="Choose one of the results",
            min_values=1,
            max_values=1,
        )
        actionrow = create_actionrow(select)

        await ctx.send("Here are your search results!", components=[actionrow])

        while True:
            try:
                button_ctx: ComponentContext = await wait_for_component(
                    self.client, components=actionrow, timeout=120
                )

                selected: int = int(button_ctx.selected_options[0])
                selected = await anilist.get(id=selected, content_type=media)

                if media == "anime":
                    selected: CAnime = CAnime.create(selected)
                elif media == "manga":
                    selected: CManga = CManga.create(selected)

                embed = await selected.send_embed()

                select = create_select(
                    options=[
                        create_select_option(
                            label=(
                                i.title.romaji
                                if len(i.title.romaji) <= 25
                                else i.title.romaji[:22] + "..."
                            ),
                            description=(
                                i.title.english
                                if len(i.title.english) <= 50
                                else i.title.english[:47] + "..."
                            ),
                            value=str(i.id),
                            default=(str(i.id) == str(selected.id)),
                        )
                        for i in results
                    ],
                    placeholder="Choose one of the results",
                    min_values=1,
                    max_values=1,
                )
                actionrow = create_actionrow(select)

                await button_ctx.edit_origin(
                    content="Here are your search results!",
                    components=[actionrow],
                    embed=embed,
                )

            except:
                break

        return

    @cog_ext.cog_slash(
        name="setup",
        description="Setup activity feed in current channel.",
        guild_ids=get_debug_guild_id(),
        options=[
            create_option(
                name="username",
                description="AniList username.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
            create_option(
                name="type",
                description="Activity type. (Default: Anime)",
                option_type=SlashCommandOptionType.INTEGER,
                required=False,
                choices=[
                    create_choice(name=k.title(), value=v) for k, v in Feed.TYPE.items()
                ],
            ),
        ],
    )
    async def _setup(
        self, ctx: SlashContext, username: str, type: int = Feed.TYPE["ANIME"]
    ):

        if not ctx.author.permissions_in(ctx.channel).manage_webhooks:
            await ctx.send(
                "You don't have the permission to use this command.", hidden=True
            )
            return

        await ctx.defer(hidden=True)

        user: Activity = await Activity.create(username, ctx.channel, int(type))

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

        if user not in [
            i for i in self.feeds if i.type == user.type and i.channel == user.channel
        ]:
            self.feeds.append(user)
            await database.feed_insert([user.JSON()])
            embed = discord.Embed(
                title="Done!",
                description=f"This channel will now track the {list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(type)].lower()} list of {user.username}",
                color=color_done,
            )
        else:
            embed = discord.Embed(
                title="Could not start tracking!",
                description=f"This channel is already tracking {user.username}'s {list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(type)].lower()} list!",
                color=color_warn,
            )

        await user.get_feed(user.feed)
        await user.feed.process_entries(
            user.feed.type.send_embed,
            channel=user.channel,
            profile=user.profile,
        )

        await ctx.send(" ឵឵", embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="remove",
        description="Remove active feed in current channel.",
        guild_ids=get_debug_guild_id(),
        options=[
            create_option(
                name="username",
                description="AniList username.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
            create_option(
                name="type",
                description="Activity type. (Default: Anime)",
                option_type=SlashCommandOptionType.INTEGER,
                required=False,
                choices=[
                    create_choice(name=k.title(), value=v) for k, v in Feed.TYPE.items()
                ],
            ),
        ],
    )
    async def _remove(
        self, ctx: SlashContext, username: str, type: int = Feed.TYPE["ANIME"]
    ):

        if not ctx.author.permissions_in(ctx.channel).manage_webhooks:
            await ctx.send(
                "You don't have the permission to use this command.", hidden=True
            )
            return

        await ctx.defer(hidden=True)

        if any(
            user
            for user in self.feeds
            if (
                user.username == username
                and user.channel == ctx.channel
                and user.type == type
            )
        ):
            user = next(
                user
                for user in self.feeds
                if (
                    user.username == username
                    and user.channel == ctx.channel
                    and user.type == type
                )
            )
            self.feeds.remove(user)
            await database.feed_remove([user.JSON()])
            embed = discord.Embed(
                title="Done!",
                description=f"This channel will now stop tracking the {list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(type)].lower()} list of {user.username}",
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
        guild_ids=get_debug_guild_id(),
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

        def format_str(feed: Activity) -> str:
            if scope == SCOPE["This channel"]:
                return (
                    feed.username
                    + f" ({list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(type)].title()})"
                )
            elif scope == SCOPE["Whole server"]:
                return (
                    feed.username
                    + f" ({list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(type)].title()})"
                    + " -> #"
                    + feed.channel.name
                )

        await ctx.send(
            "```\n" + "\n".join((format_str(feed) for feed in items)) + "```",
            hidden=True,
        )

    @cog_ext.cog_slash(
        name="profile",
        description="Get user profile.",
        guild_ids=get_debug_guild_id(),
        options=[
            create_option(
                name="username",
                description="AniList username.",
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
