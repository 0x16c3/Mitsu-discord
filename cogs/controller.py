# discord imports
from os import terminal_size
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
from .api.types import CCharacter, CUser, CAnime, CManga, CListActivity, CTextActivity
from typing import Union


class Feed:

    TYPE = {"ANIME": 0, "MANGA": 1, "TEXT": 2}

    @staticmethod
    def get_type(i: any):
        return list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(i)]

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
            if not len(feed):
                logger.debug("Could not initialize " + str(self))
                return

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
        t: Union[str, int] = "ANIME",
    ) -> None:
        self.username = username
        self.channel = channel
        self.profile = profile

        self.type = Feed.TYPE[t] if isinstance(t, str) else t
        self.feed = Feed(username, self.type)

        self.loop = None

    @staticmethod
    async def create(
        username: str,
        channel: discord.TextChannel,
        t: Union[int, str] = "ANIME",
        profile: CUser = None,
    ) -> "Activity":

        if not profile:
            try:
                profile = await anilist.get_user(name=username)
                profile = CUser.create(profile)
            except:
                return None

        return Activity(username, channel, profile, t)

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
        return "<Activity: {}:{}:{}>".format(
            self.username, str(self.channel.id), str(self.type)
        )

    def __eq__(self, o: "Activity"):
        return "<Activity: {}:{}:{}>".format(
            self.username, str(self.channel.id), str(self.type)
        ) == str(o)

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

            enable_filter = not user.channel.is_nsfw()

            await user.get_feed(user.feed)
            await user.feed.process_entries(
                user.feed.type.send_embed,
                channel=user.channel,
                anilist=anilist,
                filter_adult=enable_filter,
            )

        logger.info(f"Loaded {len(self.feeds)}.")

    async def process(self):

        while True:

            await asyncio.sleep(int(config["INTERVAL"]))

            for user in self.feeds:
                user: Activity

                enable_filter = not user.channel.is_nsfw()

                await user.get_feed(user.feed)
                await user.feed.process_entries(
                    user.feed.type.send_embed,
                    channel=user.channel,
                    anilist=anilist,
                    filter_adult=enable_filter,
                )

    @cog_ext.cog_slash(
        name="activity",
        description="Setup / manage an activity feed in the current channel.",
        guild_ids=get_debug_guild_id(),
        options=[
            create_option(
                name="username",
                description="AniList username.",
                option_type=SlashCommandOptionType.STRING,
                required=True,
            ),
        ],
    )
    async def _activity(self, ctx: SlashContext, username: str):

        if not ctx.author.permissions_in(ctx.channel).manage_webhooks:
            await ctx.send(
                "You don't have the permission to use this command.", hidden=True
            )
            return

        select = create_select(
            custom_id="_activity0",
            options=[
                create_select_option(
                    label=k.title(),
                    value=str(v),
                    default=(
                        v
                        in [
                            f.type
                            for f in self.feeds
                            if f.username == username and f.channel == ctx.channel
                        ]
                    ),
                )
                for k, v in Feed.TYPE.items()
            ],
            placeholder="Choose the activities you want to track.",
            min_values=0,
            max_values=len(Feed.TYPE),
        )
        actionrow = create_actionrow(select)

        message = await ctx.send(
            content="Setting up activity feed", components=[actionrow], hidden=False
        )

        def check_author(cctx: ComponentContext):
            return ctx.author.id == cctx.author.id

        selected = []

        while True:

            try:
                button_ctx: ComponentContext = await wait_for_component(
                    self.client, components=[actionrow], check=check_author, timeout=15
                )

                selected: List[int] = [int(i) for i in button_ctx.selected_options]
                await button_ctx.defer(edit_origin=True)

                select = create_select(
                    custom_id="_activity1",
                    options=[
                        create_select_option(
                            label=k.title(),
                            value=str(v),
                            default=v in selected,
                        )
                        for k, v in Feed.TYPE.items()
                    ],
                    placeholder="Choose the activities you want to track.",
                    min_values=0,
                    max_values=len(Feed.TYPE),
                    disabled=False,
                )
                actionrow = create_actionrow(select)
                await message.edit(
                    content="Setting up activity feed",
                    components=[actionrow],
                )
            except:
                select = create_select(
                    custom_id="_activity1",
                    options=[
                        create_select_option(
                            label=k.title(),
                            value=str(v),
                            default=v in selected,
                        )
                        for k, v in Feed.TYPE.items()
                    ],
                    placeholder="Choose the activities you want to track.",
                    min_values=0,
                    max_values=len(Feed.TYPE),
                    disabled=True,
                )
                actionrow = create_actionrow(select)
                await message.edit(
                    content="Setting up activity feed",
                    components=[actionrow],
                )
                return

            activities = []
            activities_failed = []

            try:
                profile = await anilist.get_user(name=username)
                profile = CUser.create(profile)
            except:
                embed = discord.Embed(
                    title="Could not start tracking!",
                    description=(
                        "There has been an error fetching this profile.\n"
                        "Please double-check the username or try again later."
                    ),
                    color=color_errr,
                )
                await button_ctx.edit_origin("An error occured!", embed=embed)
                return

            user = None

            for i in selected:
                user: Activity = await Activity.create(
                    username, ctx.channel, i, profile
                )

                if not user:
                    activities_failed.append(
                        f"`{list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(i)].title()}`"
                    )
                    continue

                if user not in [
                    i
                    for i in self.feeds
                    if i.type == user.type and i.channel == user.channel
                ]:
                    self.feeds.append(user)
                    await database.feed_insert([user.JSON()])
                    activities.append(
                        f"`Started {list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(i)].lower()}`"
                    )
            for i in [
                x
                for x in self.feeds
                if x.username == username
                and x.channel == ctx.channel
                and x.type not in selected
            ]:
                self.feeds.remove(i)
                await database.feed_remove([i.JSON()])
                activities.append(
                    f"`Stopped {list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(int(i.type))].lower()}`"
                )

            embed = discord.Embed(
                title="Done!",
                description=f"This channel will now track the following activities of {username}",
                color=color_done if len(activities_failed) == 0 else color_warn,
            )
            if len(activities) >= 1:
                embed.add_field(name="Tracking", value="\n".join(activities))
            if len(activities_failed) >= 1:
                embed.add_field(
                    name="Could Not Start Tracking", value="\n".join(activities_failed)
                )

            await message.edit(content="Done!", embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="edit",
        description="Manage active feeds in the current channel.",
        guild_ids=get_debug_guild_id(),
    )
    async def _edit(self, ctx: SlashContext):

        if not ctx.author.permissions_in(ctx.channel).manage_webhooks:
            await ctx.send(
                "You don't have the permission to use this command.", hidden=True
            )
            return

        items = [
            feed
            for feed in self.feeds
            if feed and feed.channel and feed.channel == ctx.channel
        ]

        if not len(items):
            await ctx.send(
                f"No active feeds in this channel",
                hidden=True,
            )
            return

        select = create_select(
            custom_id="_edit0",
            options=[
                create_select_option(
                    label=i if len(i) <= 25 else i[:22] + "...",
                    description=", ".join(
                        [Feed.get_type(f.type) for f in items if f.username == i]
                    ),
                    value=i,
                )
                for i in list(set([item.username for item in items]))
            ],
            placeholder="Choose one of the feeds.",
            min_values=1,
            max_values=1,
        )
        actionrow = create_actionrow(select)

        message = await ctx.send(
            content="Active feeds in this channel", components=[actionrow], hidden=False
        )

        def check_author(cctx: ComponentContext):
            return ctx.author.id == cctx.author.id

        while True:
            try:
                button_ctx: ComponentContext = await wait_for_component(
                    self.client, components=actionrow, check=check_author, timeout=30
                )

                username: str = button_ctx.selected_options[0]
                all_types = [
                    feed
                    for feed in self.feeds
                    if feed.channel == ctx.channel and feed.username == username
                ]

                select = create_select(
                    custom_id="_edit1",
                    options=[
                        create_select_option(
                            label=(i if len(i) <= 25 else (i[:22] + "...")),
                            description=", ".join(
                                [Feed.get_type(i.type) for i in all_types]
                            ),
                            value=i,
                            default=(username == i),
                        )
                        for i in list(set([item.username for item in items]))
                    ],
                    placeholder="Choose one of the feeds.",
                    min_values=1,
                    max_values=1,
                )
                actionrow = create_actionrow(select)

                select_feed = create_select(
                    custom_id="_activeSub0",
                    options=[
                        create_select_option(
                            label=k.title(),
                            value=str(v),
                            default=v in [i.type for i in all_types],
                        )
                        for k, v in Feed.TYPE.items()
                    ],
                    placeholder="Choose the activities you want to track.",
                    min_values=0,
                    max_values=len(Feed.TYPE),
                    disabled=False,
                )
                actionrow_feed = create_actionrow(select_feed)

                await button_ctx.edit_origin(
                    content="Active feeds in this channel",
                    components=[actionrow, actionrow_feed],
                )

                selected = []

                while True:

                    try:
                        button_ctx: ComponentContext = await wait_for_component(
                            self.client,
                            components=[actionrow_feed],
                            check=check_author,
                            timeout=15,
                        )

                        selected: List[int] = [
                            int(i) for i in button_ctx.selected_options
                        ]
                        await button_ctx.defer(edit_origin=True)

                        select = create_select(
                            custom_id="_edit1",
                            options=[
                                create_select_option(
                                    label=(i if len(i) <= 25 else (i[:22] + "...")),
                                    description=", ".join(
                                        [Feed.get_type(i.type) for i in all_types]
                                    ),
                                    value=i,
                                    default=(username == i),
                                )
                                for i in list(set([item.username for item in items]))
                            ],
                            placeholder="Choose one of the feeds.",
                            min_values=1,
                            max_values=1,
                            disabled=False,
                        )
                        actionrow = create_actionrow(select)

                        select_feed = create_select(
                            custom_id="_editSub1",
                            options=[
                                create_select_option(
                                    label=k.title(),
                                    value=str(v),
                                    default=v in selected,
                                )
                                for k, v in Feed.TYPE.items()
                            ],
                            placeholder="Choose the activities you want to track.",
                            min_values=0,
                            max_values=len(Feed.TYPE),
                            disabled=False,
                        )
                        actionrow_feed = create_actionrow(select_feed)
                        await message.edit(
                            content=f"Active feeds in this channel",
                            components=[actionrow, actionrow_feed],
                        )
                    except:
                        select = create_select(
                            custom_id="_edit1",
                            options=[
                                create_select_option(
                                    label=(i if len(i) <= 25 else (i[:22] + "...")),
                                    description=", ".join(
                                        [Feed.get_type(i.type) for i in all_types]
                                    ),
                                    value=i,
                                    default=(username == i),
                                )
                                for i in list(set([item.username for item in items]))
                            ],
                            placeholder="Choose one of the feeds.",
                            min_values=1,
                            max_values=1,
                            disabled=True,
                        )
                        actionrow = create_actionrow(select)

                        select_feed = create_select(
                            custom_id="_editSub1",
                            options=[
                                create_select_option(
                                    label=k.title(),
                                    value=str(v),
                                    default=v in selected,
                                )
                                for k, v in Feed.TYPE.items()
                            ],
                            placeholder="Choose the activities you want to track.",
                            min_values=0,
                            max_values=len(Feed.TYPE),
                            disabled=True,
                        )
                        actionrow_feed = create_actionrow(select_feed)
                        await message.edit(
                            content=f"Active feeds in this channel",
                            components=[actionrow, actionrow_feed],
                        )
                        return

                    activities = []
                    activities_failed = []

                    try:
                        profile = await anilist.get_user(name=username)
                        profile = CUser.create(profile)
                    except:
                        embed = discord.Embed(
                            title="Could not start tracking!",
                            description=(
                                "There has been an error fetching this profile.\n"
                                "Please double-check the username or try again later."
                            ),
                            color=color_errr,
                        )
                        await button_ctx.edit_origin("An error occured!", embed=embed)
                        return

                    user = None

                    for i in selected:
                        user: Activity = await Activity.create(
                            username, ctx.channel, i, profile
                        )

                        if not user:
                            activities_failed.append(
                                f"`{list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(i)].title()}`"
                            )
                            continue

                        if user not in [
                            i
                            for i in self.feeds
                            if i.type == user.type and i.channel == user.channel
                        ]:
                            self.feeds.append(user)
                            await database.feed_insert([user.JSON()])
                            activities.append(
                                f"`Started {list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(i)].lower()}`"
                            )
                    for i in [
                        x
                        for x in self.feeds
                        if x.username == username and x.type not in selected
                    ]:
                        self.feeds.remove(i)
                        await database.feed_remove([i.JSON()])
                        activities.append(
                            f"`Stopped {list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(int(i.type))].lower()}`"
                        )

                    embed = discord.Embed(
                        title="Done!",
                        description=f"This channel will now track the following activities of {username}",
                        color=color_done if len(activities_failed) == 0 else color_warn,
                    )
                    if len(activities) >= 1:
                        embed.add_field(name="Tracking", value="\n".join(activities))
                    if len(activities_failed) >= 1:
                        embed.add_field(
                            name="Could Not Start Tracking",
                            value="\n".join(activities_failed),
                        )

                    await button_ctx.edit_origin(
                        content=f"Active feeds in this channel",
                        components=[actionrow, actionrow_feed],
                        embed=embed,
                    )

            except:
                await message.delete()
                break

        return

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
                    + f" ({list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(feed.type)].title()})"
                )
            elif scope == SCOPE["Whole server"]:
                return (
                    feed.username
                    + f" ({list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(feed.type)].title()})"
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
    async def _get_profile(self, ctx: SlashContext, username: str, **kwargs):
        if not "send-message" in kwargs:
            kwargs["send-message"] = False

        send_message = not kwargs["send-message"]
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
            await ctx.send("An error occured!", embed=embed, hidden=True)
            return

        embed = await profile.send_embed()
        await ctx.send("Done!", embed=embed, hidden=send_message)

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
                    create_choice(name="Character", value="character"),
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
            custom_id="_search0",
            options=[
                create_select_option(
                    label=(
                        (
                            i.title.romaji
                            if len(i.title.romaji) <= 25
                            else i.title.romaji[:22] + "..."
                        )
                        if media != "character"
                        else (
                            i.name.full
                            if len(i.name.full) <= 25
                            else i.name.full[:22] + "..."
                        )
                    ),
                    description=(
                        (
                            (
                                i.title.english
                                if len(i.title.english) <= 50
                                else i.title.english[:47] + "..."
                            )
                            if hasattr(i.title, "english")
                            else (
                                i.title.native
                                if len(i.title.native) <= 50
                                else i.title.native[:47] + "..."
                            )
                        )
                        if media != "character"
                        else None
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

        message = await ctx.send(
            content=f"Search results for {query}", components=[actionrow]
        )

        def check_author(cctx: ComponentContext):
            return ctx.author.id == cctx.author.id

        while True:
            try:
                button_ctx: ComponentContext = await wait_for_component(
                    self.client, components=actionrow, check=check_author, timeout=30
                )

                selected: int = int(button_ctx.selected_options[0])
                selected = await anilist.get(id=selected, content_type=media)

                if media == "anime":
                    selected: CAnime = CAnime.create(selected)
                elif media == "manga":
                    selected: CManga = CManga.create(selected)
                elif media == "character":
                    selected: CCharacter = CCharacter.create(selected)

                enable_filter = not ctx.channel.is_nsfw()
                embed = await selected.send_embed(filter_adult=enable_filter)

                select = create_select(
                    custom_id="_search1",
                    options=[
                        create_select_option(
                            label=(
                                (
                                    i.title.romaji
                                    if len(i.title.romaji) <= 25
                                    else i.title.romaji[:22] + "..."
                                )
                                if media != "character"
                                else (
                                    i.name.full
                                    if len(i.name.full) <= 25
                                    else i.name.full[:22] + "..."
                                )
                            ),
                            description=(
                                (
                                    (
                                        i.title.english
                                        if len(i.title.english) <= 50
                                        else i.title.english[:47] + "..."
                                    )
                                    if hasattr(i.title, "english")
                                    else (
                                        i.title.native
                                        if len(i.title.native) <= 50
                                        else i.title.native[:47] + "..."
                                    )
                                )
                                if media != "character"
                                else None
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
                    content=f"Search results for {query}",
                    components=[actionrow],
                    embed=embed,
                )

            except:
                select = create_select(
                    custom_id="_search2",
                    options=[
                        create_select_option(
                            label="Expired", description="Expired", value="-1"
                        )
                    ],
                    placeholder="Choose one of the results (Expired)",
                    min_values=1,
                    max_values=1,
                    disabled=True,
                )
                actionrow = create_actionrow(select)
                await message.edit(
                    content="Done!",
                    components=[actionrow],
                )
                break

        return


def setup(client):
    client.add_cog(Controller(client))
