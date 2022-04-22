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
from .api.types import CCharacter, CUser, CAnime, CManga, CListActivity, CTextActivity
from typing import Union
import sys


class Feed:
    """AniList feed object that interfaces with the AniList api.

    Args:
        username (str): Username of the profile
        userid (int): User id of the profile
        feed (int): Feed type

    Attributes:
        username (str): Username of the profile
        feed (int): Feed type
        function (method): Function to fetch new activities
        arguments (dict): Arguments to pass to the function
        type: Excpected activity object type
    """

    TYPE = {"ANIME": 0, "MANGA": 1, "TEXT": 2}

    @staticmethod
    def get_type(i: any):
        return list(Feed.TYPE.keys())[list(Feed.TYPE.values()).index(i)]

    def __init__(self, username: str, userid: int, feed: int) -> None:
        self.username = username
        self.userid = userid

        self.feed = feed

        self.function = None
        self.arguments = None
        self.type = None

        self.errors = 0

        if self.feed == self.TYPE["ANIME"]:
            self.type = CListActivity
            self.function = anilist.get_activity
            self.arguments = {
                "id": self.userid,
                "content_type": "anime",
            }
        if self.feed == self.TYPE["MANGA"]:
            self.type = CListActivity
            self.function = anilist.get_activity
            self.arguments = {
                "id": self.userid,
                "content_type": "manga",
            }
        if self.feed == self.TYPE["TEXT"]:
            self.type = CTextActivity
            self.function = anilist.get_activity
            self.arguments = {
                "id": self.userid,
                "content_type": "text",
            }

        self.entries = []
        self.entries_processed = []
        self._init = False
        self.reset = False

    async def retrieve(
        self,
    ) -> Dict[
        List[Union[CListActivity, CTextActivity]],
        List[Union[CListActivity, CTextActivity]],
    ]:
        """Retrieves activity feed from AniList.

        Returns:
            List[Union[CListActivity, CTextActivity]],: First int(config["MEMORY_LIMIT"]) activities.
            List[Union[CListActivity, CTextActivity]]]: Entire activity list.
        """
        try:
            ret = await self.function(**self.arguments)

            if not isinstance(ret, list):
                ret = []

            if self.feed == self.TYPE["TEXT"]:
                msg = await anilist.get_activity(
                    id=self.username, content_type="message"
                )
                if msg:
                    ret.extend(msg)

            res = []
            for item in ret:
                obj = self.type.create(item, self.username)
                res.append(obj)

            self.errors = 0

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logger.print(
                "Error on {}: {}\n[STACK] {} {} {}".format(
                    self.username, e, exc_type, fname, exc_tb.tb_lineno
                )
            )
            self.errors += 1
            return [], []

        return res[: int(config["MEMORY_LIMIT"])], res

    async def update(self, feed: List[Union[CListActivity, CTextActivity]]) -> None:
        """Updates activity list.
        Checks for new activities.

        Args:
            feed (List[Union[CListActivity, CTextActivity]]): Latest activity feed from AniList
        """

        if not self._init or self.reset:
            if not len(feed):
                logger.debug("Empty feed " + str(self))
                return

            for item in feed:
                self.entries_processed.append(item)

            if not self.reset:
                logger.info("Initialized " + str(self))
                logger.debug(
                    "\n  List:\n   "
                    + "\n   ".join(str(x.id) for x in self.entries_processed)
                )

            self._init = True
            self.reset = False
            return

        for item in feed:
            if item.id in (i.id for i in self.entries_processed):
                continue
            if self.type == CListActivity:
                if item.media.id in (i.media.id for i in self.entries):
                    continue
                if item.media.id in (i.media.id for i in self.entries_processed):
                    # check date
                    first_occurence: CListActivity = next(
                        i for i in self.entries_processed if i.media.id == item.media.id
                    )

                    if item.date.timestamp < first_occurence.date.timestamp:
                        continue

                if item.date.timestamp < self.entries_processed[-1].date.timestamp:
                    continue

            self.entries.insert(0, item)
            self.entries = self.entries[: int(config["MEMORY_LIMIT"])]

            logger.info("Added " + str(item.id))

    async def move_item(self, item, func=None, **kwargs) -> bool:
        """Runs function on item if provided and flags it as processed.

        Args:
            item: Activity item
            func (method): Function to run. Defaults to None.

        Returns:
            bool: if the item is moved or not
        """

        processed = False
        item_old = None

        if item not in self.entries_processed:

            if func:
                try:
                    res = await func(item=item, **kwargs)

                    if isinstance(res, tuple):
                        if res[0] == "List[CListActivity]":
                            self.entries = res[1]
                            item_old = item
                            item = res[2]

                except Exception as e:

                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    logger.print(
                        "Error running function on entry {}: {}\n[STACK] {} {} {}".format(
                            item.id, e, exc_type, fname, exc_tb.tb_lineno
                        )
                    )

            if self.type == CListActivity:
                self.entries_processed.insert(0, item)
            elif self.type == CTextActivity:
                self.entries_processed.insert(0, item)
            else:
                logger.info("Unknown type " + str(self.type))

            self.entries.remove(item)
            if item_old in self.entries:
                self.entries.remove(item_old)

            self.entries_processed = self.entries_processed[
                : int(config["MEMORY_LIMIT"])
            ]

            processed = True

        return processed

    async def process_entries(self, func, **kwargs) -> None:
        """Processes current list of entries.

        Args:
            func (method): Function to run on processed items
        """

        logger.debug(str(self) + ".entries:" + str(len(self.entries)))
        logger.debug(
            str(self) + ".entries_processed:" + str(len(self.entries_processed))
        )

        processed = False

        for item in self.entries[:]:

            moved = await self.move_item(item, func, **kwargs)

            if moved:
                processed = True

        """
        if processed and len(self.entries_processed) > int(config["MEMORY_LIMIT"]):
            self.entries_processed = []
            self.entries = []
            self.reset = True

            items, items_full = await self.retrieve()
            if len(items) == 0:
                logger.info("Could not reset " + str(self) + " - FALLBACK (NEXT TICK)")
                return

            await self.update(items)

            logger.info("Reset " + str(self) + " - exceeded entry limit.")
            return
        """

        return


class Activity:
    """Activity feed object to manage / process activities.

    Args:
        username (str): Username of the profile
        channel (discord.TextChannel): Discord channel that the updates are processed in
        profile (CUser): Cached user profile for extra information
        t (Union[str, int]): Feed type. Defaults to "ANIME".

    Attributes:
        username (str): Username of the profile
        channel (discord.TextChannel): Discord channel that the updates are processed in
        profile (CUser): Cached user profile for extra information
        type (Feed.TYPE): Feed type
        feed (Feed): Feed object
        loop: Asyncio loop
    """

    def __init__(
        self,
        username: str,
        userid: int,
        channel: discord.TextChannel,
        profile: CUser,
        t: Union[str, int] = "ANIME",
    ) -> None:
        self.username = username
        self.userid = userid
        self.channel = channel
        self.profile = profile

        self.type = Feed.TYPE[t] if isinstance(t, str) else t
        self.feed = Feed(username, userid, self.type)

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

        return Activity(username, profile.id, channel, profile, t)

    async def get_feed(
        self, feed: Feed = None
    ) -> Dict[
        List[Union[CListActivity, CTextActivity]],
        List[Union[CListActivity, CTextActivity]],
    ]:
        """Returns feed items from the feed

        Args:
            feed (Feed): Feed to get items. Defaults to self.feed.

        Returns:
            List[Union[CListActivity, CTextActivity]],: First 15 activities.
            List[Union[CListActivity, CTextActivity]]]: Entire activity list.
        """

        if not feed:
            feed = self.feed

        items, items_full = await feed.retrieve()

        await feed.update(items)
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
    """Dicord cog to control commands and the active feeds.

    Attributes:
        client: Discord client instance
        feeds (List[Activity]): Active feeds
    """

    def __init__(self, client):
        self.client = client
        self.feeds: List[Activity] = []
        self.loaded = False

    async def on_ready(self):
        """Loads saved feeds from the database."""

        channels = await database.channel_get()
        for ch in channels:
            await database.channel_repair(ch["channel"])

        items = await database.feed_get()

        logger.info(
            f"Loading {len(items)} feed{'s' if len(items) > 1 else ''} that exist in the database."
        )

        error_channel_ids = []

        for i, item in enumerate(items):
            channel: discord.TextChannel = self.client.get_channel(int(item["channel"]))

            if item in self.feeds:
                continue

            if not channel:
                logger.debug(
                    f"Could not load <{item['username']}:{item['channel']}:{item['type']}>"
                )
                await database.feed_remove([item])
                continue

            permissions = channel.permissions_for(channel.guild.me)
            if not permissions:
                logger.debug(
                    f"Could not load <{item['username']}:{item['channel']}:{item['type']}> - Invalid permissions"
                )
                continue
            elif not permissions.send_messages:

                if channel.id not in error_channel_ids:
                    guild = channel.guild
                    owner = guild.get_member(guild.owner_id)

                    embed = discord.Embed(
                        title="`Warning`",
                        description=f"Missing Access\nCannot send messages to channel `#{channel.name}`",
                        color=color_warn,
                    )
                    embed.add_field(
                        name="Error",
                        value="```The feed has been automatically removed.\n"
                        "Please setup a feed again after giving Mitsu the 'Send Messages' permission.```",
                    )

                    try:
                        await owner.send(embed=embed)
                    except:
                        pass

                    error_channel_ids.append(channel.id)

                logger.debug(
                    f"Could not load <{item['username']}:{item['channel']}:{item['type']}> - Incorrect permissions"
                )
                await database.feed_remove([item])
                continue

            user: Activity = await Activity.create(
                item["username"], channel, int(item["type"])
            )

            if not user:
                logger.debug(
                    f"Could not load <{item['username']}:{item['channel']}:{item['type']}>"
                )
                await database.feed_remove([item])
                continue

            self.feeds.append(user)

            # wait 60 seconds after every 90 activity to prevent rate limiting
            if i % 90 == 0 and i >= 90:
                logger.debug(f"Waiting 60 seconds.")
                await asyncio.sleep(60)

        if len(self.feeds) > 30:
            logger.info(f"Created Activity objects, waiting 60 seconds to fetch feeds.")
            await asyncio.sleep(60)

        for i, user in enumerate(self.feeds):
            user: Activity

            enable_filter = not user.channel.is_nsfw()

            await user.get_feed(user.feed)
            await user.feed.process_entries(
                user.feed.type.send_embed,
                channel=user.channel,
                anilist=anilist,
                filter_adult=enable_filter,
                activity=user,
            )

            # wait 60 seconds after every 45 feeds to prevent rate limiting
            if i % 45 == 0 and i >= 45:
                logger.debug(f"Waiting 60 seconds.")
                await asyncio.sleep(60)

        logger.info(f"Loaded {len(self.feeds)}.")
        self.loaded = True
        del error_channel_ids

    async def process(self):
        """Processes all feeds with the specified interval in the config file."""

        while True:

            if not self.loaded:
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(int(config["INTERVAL"]))

            for i, user in enumerate(self.feeds):
                user: Activity

                enable_filter = not user.channel.is_nsfw()

                await user.get_feed(user.feed)
                await user.feed.process_entries(
                    user.feed.type.send_embed,
                    channel=user.channel,
                    anilist=anilist,
                    filter_adult=enable_filter,
                    activity=user,
                )

                # wait 60 seconds after every 30 feeds to prevent rate limiting
                if i % 45 == 0 and i >= 45:
                    logger.debug(f"Waiting 60 seconds.")
                    await asyncio.sleep(60)

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

        permissions = ctx.channel.permissions_for(ctx.guild.me)
        if not permissions or not permissions.send_messages:
            embed = discord.Embed(
                title="`Warning`",
                description=f"Missing Access\nCannot send messages to this channel.",
                color=color_warn,
            )
            embed.add_field(
                name="Error",
                value="```Please grant Mitsu the 'Send Messages' permission\n"
                "and try again.```",
            )
            await ctx.send("Incorrect permissions", embed=embed, hidden=True)
            return

        select = create_select(
            custom_id="_activity0",
            options=[
                create_select_option(
                    label=k.title()[:25],
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
                            label=k.title()[:25],
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
                            label=k.title()[:25],
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
                await button_ctx.edit_origin(content="An error occured!", embed=embed)
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
                            label=k.title()[:25],
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
                                    label=k.title()[:25],
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
                                    label=k.title()[:25],
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

                    user = None
                    profile = None

                    for i in selected:

                        if not profile:
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
                                await button_ctx.edit_origin(
                                    content="An error occured!", embed=embed
                                )
                                return

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
                try:
                    await message.delete()
                except discord.errors.NotFound:
                    pass

                break

        return

    @cog_ext.cog_slash(
        name="filter",
        description="Filter list activity types for this channel.",
        guild_ids=get_debug_guild_id(),
    )
    async def _filter(self, ctx: SlashContext):

        if not ctx.author.permissions_in(ctx.channel).manage_webhooks:
            await ctx.send(
                "You don't have the permission to use this command.", hidden=True
            )
            return

        channels = await database.channel_get()
        matching = [
            channel for channel in channels if int(channel["channel"]) == ctx.channel.id
        ]
        if len(matching):
            current = matching[0]
        else:
            current = {
                "channel": ctx.channel.id,
                "list_block_progress": False,
                "list_block_completion": False,
                "list_block_planning": False,
                "list_block_dropped": False,
                "list_block_paused": False,
            }

        select = create_select(
            custom_id="_filter0",
            options=[
                create_select_option(
                    label=i.capitalize(),
                    value=i,
                    default=not current[f"list_block_{i}"],
                )
                for i in ["progress", "completion", "planning", "dropped", "paused"]
            ],
            max_values=5,
            placeholder="Filter enabled list activities for this channel.",
        )
        actionrow = create_actionrow(select)

        message = await ctx.send(
            content="Select list activity filters", components=[actionrow], hidden=False
        )

        def check_author(cctx: ComponentContext):
            return ctx.author.id == cctx.author.id

        while True:
            try:
                button_ctx: ComponentContext = await wait_for_component(
                    self.client,
                    components=[actionrow],
                    check=check_author,
                    timeout=30,
                )

                selected: List[str] = [i for i in button_ctx.selected_options]
                await button_ctx.defer(edit_origin=True)

                for i in ["progress", "planning", "dropped", "paused"]:
                    if i in selected and current[f"list_block_{i}"]:
                        current[f"list_block_{i}"] = False
                    elif i not in selected and not current[f"list_block_{i}"]:
                        current[f"list_block_{i}"] = True

                channels = await database.channel_get()
                matching = [
                    channel
                    for channel in channels
                    if int(channel["channel"]) == ctx.channel.id
                ]
                if len(matching):
                    await database.channel_update(ctx.channel.id, current)
                else:
                    await database.channel_insert([current])

                select = create_select(
                    custom_id="_filter1",
                    options=[
                        create_select_option(
                            label=i.capitalize(),
                            value=i,
                            default=not current[f"list_block_{i}"],
                        )
                        for i in [
                            "progress",
                            "completion",
                            "planning",
                            "dropped",
                            "paused",
                        ]
                    ],
                    max_values=5,
                    placeholder="Filter enabled list activities for this channel.",
                )
                actionrow = create_actionrow(select)

                await message.edit(
                    content=f"Select list activity filters", components=[actionrow]
                )
            except:
                select = create_select(
                    custom_id="_filter2",
                    options=[
                        create_select_option(
                            label=i.capitalize(),
                            value=i,
                            default=not current[f"list_block_{i}"],
                        )
                        for i in [
                            "progress",
                            "completion",
                            "planning",
                            "dropped",
                            "paused",
                        ]
                    ],
                    max_values=5,
                    placeholder="Filter enabled list activities for this channel.",
                    disabled=True,
                )
                actionrow = create_actionrow(select)

                await message.edit(
                    content=f"Select list activity filters",
                    components=[actionrow],
                )
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
            query, content_type=media, page=1, limit=5, pagination=False
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
