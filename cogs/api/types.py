# discord imports
import discord
import asyncio

# utilities
import re
from PIL import Image
import urllib.request, io
from typing import Optional, Tuple, Union
from ..utils import *
from .database import database

# anilist
from anilist import AsyncClient
from anilist.types import (
    Anime,
    Manga,
    ListActivity,
    TextActivity,
    User,
    FavouritesUnion,
    StatisticsUnion,
    Character,
    Staff,
    Studio,
    MediaList,
    NextAiring,
    Statistic,
    Title,
)


class CAnime(Anime):
    def create(obj: Anime) -> "CAnime":
        obj.__class__ = CAnime
        return obj

    async def send_embed(
        self, channel: discord.TextChannel = None, filter_adult: bool = True
    ) -> Optional[discord.Embed]:
        embed = discord.Embed(
            title=self.title.romaji,
            url=self.url,
            description=self.title.english
            if hasattr(self.title, "english")
            else self.title.native,
            color=color_main,
        )

        ranking = None
        if hasattr(self, "rankings"):
            ranking = self.rankings[0]
        embed.add_field(
            name="Stats 🧮",
            value=(
                (
                    (
                        f"Aired <t:{self.start_date.get_timestamp()}:D> to <t:{self.end_date.get_timestamp()}:D>\n"
                        if hasattr(self, "end_date")
                        and self.end_date.get_timestamp() != -1
                        else (
                            f"Airing since <t:{self.start_date.get_timestamp()}:R>\n"
                            + (
                                f"Next episode: <t:{self.next_airing.at.get_timestamp()}:R> (Episode {self.next_airing.episode})\n"
                                if hasattr(self, "next_airing")
                                else ""
                            )
                        )
                    )
                    if hasattr(self, "start_date")
                    else ""
                )
                + (
                    f"Premiered {self.season.name.title()} {self.season.year}\n"
                    if hasattr(self, "season")
                    and hasattr(self.season, "name")
                    and hasattr(self.season, "year")
                    else "Not Premiered Yet\n"
                )
                + (
                    f"> Score ⭐: `{string(self.score.mean)}`\n"
                    if hasattr(self.score, "mean")
                    else ""
                )
                + (
                    f"> Rank 📈: `#{string(ranking.rank)} on {ranking.format} ({str(ranking.year) if not ranking.all_time else 'All time'})`\n"
                    if ranking
                    else ""
                )
                + (
                    f"> Popularity 📈: `#{string(self.popularity)}`\n"
                    if hasattr(self, "popularity")
                    else ""
                )
                + f"Description 📔: \n> {string(strip_tags(self.description[:128])) + ('...' if len(string(strip_tags(self.description))) > 128 else '')}"
            ),
            inline=False,
        )
        if (hasattr(self, "is_adult") and self.is_adult) and filter_adult:
            embed.set_image(url=f"https://mitsu.0x16c3.com/filter/media/{self.id}")
        else:
            embed.set_image(url=f"https://img.anili.st/media/{self.id}")

        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.info(f"Cannot send message -> {str(channel.id)} : {self.id} {e}")
        else:
            return embed


class CManga(Manga):
    def create(obj: Manga) -> "CManga":
        obj.__class__ = CManga
        return obj

    async def send_embed(
        self, channel: discord.TextChannel = None, filter_adult: bool = True
    ) -> Optional[discord.Embed]:
        embed = discord.Embed(
            title=self.title.romaji,
            url=self.url,
            description=self.title.english
            if hasattr(self.title, "english")
            else self.title.native,
            color=color_main,
        )

        ranking = None
        if hasattr(self, "rankings"):
            ranking = self.rankings[0]
        embed.add_field(
            name="Stats 🧮",
            value=(
                (
                    (
                        f"Released <t:{self.start_date.get_timestamp()}:D> to <t:{self.end_date.get_timestamp()}:D>\n"
                        if hasattr(self, "end_date")
                        and self.end_date.get_timestamp() != -1
                        else f"Releasing since <t:{self.start_date.get_timestamp()}:R>\n"
                    )
                    if hasattr(self, "start_date")
                    else ""
                )
                + (
                    f"> Score ⭐: `{string(self.score.mean)}`\n"
                    if hasattr(self.score, "mean")
                    else ""
                )
                + (
                    f"> Rank 📈: `#{string(ranking.rank)} on {ranking.format} ({str(ranking.year) if not ranking.all_time else 'All time'})`\n"
                    if ranking
                    else ""
                )
                + (
                    f"> Popularity 📈: `#{string(self.popularity)}`\n"
                    if hasattr(self, "popularity")
                    else ""
                )
                + f"Description 📔: \n> {string(strip_tags(self.description[:128])) + ('...' if len(string(strip_tags(self.description))) > 128 else '')}"
            ),
            inline=False,
        )
        if (hasattr(self, "is_adult") and self.is_adult) and filter_adult:
            embed.set_image(url=f"https://mitsu.0x16c3.com/filter/media/{self.id}")
        else:
            embed.set_image(url=f"https://img.anili.st/media/{self.id}")

        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.info(f"Cannot send message -> {str(channel.id)} : {self.id} {e}")
        else:
            return embed


class CCharacter(Character):
    def create(obj: Character) -> "CCharacter":
        obj.__class__ = CCharacter
        return obj

    async def send_embed(
        self, channel: discord.TextChannel = None, **kwargs
    ) -> Optional[discord.Embed]:

        description_formatted = None
        if hasattr(self, "description"):
            description_formatted = self.description.replace("~!", "\n||")
            description_formatted = description_formatted.replace("!~", "||")

            description_formatted = description_formatted[:512] + (
                "..." if len(description_formatted) > 512 else ""
            )

            if description_formatted.count("||") % 2 != 0:
                description_formatted = description_formatted[:-3] + "||..."

        embed = discord.Embed(
            title=self.name.full,
            url=self.url,
            description=description_formatted,
            color=color_main,
        )

        embed.set_image(url=f"https://mitsu.0x16c3.com/character/{self.id}")

        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.info(f"Cannot send message -> {str(channel.id)} : {self.id} {e}")
        else:
            return embed


class CUser(User):
    @staticmethod
    def create(obj: User) -> "CUser":
        obj.__class__ = CUser
        return obj

    def get_color_list(self, amount: int, rotate: int = -75):
        colors = []

        for step in range(amount):
            colors.append(rotate_hue(self.profile_color, (step + 1) / amount * -rotate))

        return colors

    def get_picture_color(self) -> int:

        req = urllib.request.Request(
            self.image.medium,
            data=None,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
            },
        )

        path = io.BytesIO(urllib.request.urlopen(req).read())
        img = Image.open(path)

        unique_colors = set()
        for i in range(img.size[0]):
            for j in range(img.size[1]):
                pixel = img.getpixel((i, j))
                unique_colors.add(pixel)

        colors = img.getcolors(len(unique_colors))

        max_occurence, most_present = 0, 0
        try:
            for c in colors:
                if c[0] > max_occurence:
                    (max_occurence, most_present) = c
            return most_present
        except Exception as e:
            logger.debug(str(e))

    async def send_embed(
        self, channel: discord.TextChannel = None, **kwargs
    ) -> Optional[discord.Embed]:
        loop = asyncio.get_event_loop()

        estimate = await loop.run_in_executor(None, self.get_picture_color)
        if isinstance(estimate, int):
            estimate = [estimate, estimate, estimate]

        colors = len(estimate) - 1

        if colors < 0:
            color = color_main
        else:
            color = discord.Color.from_rgb(
                estimate[0], estimate[min(1, colors)], estimate[min(2, colors)]
            )

        embed = discord.Embed(
            title=f"{self.name}'s Profile",
            url=self.url,
            # description=str_size("\n".join("\n".split(strip_tags(self.about))[:3]))
            # if hasattr(self, "about")
            # else "No biography yet.",
            color=color,
        )
        # embed.set_thumbnail(url=self.image.large)
        embed.set_image(url=f"https://img.anili.st/user/{self.id}")

        if self.statistics.anime:
            title, content = CStatisticsUnion.create(self.statistics).embed_string(
                "anime"
            )
            embed.add_field(
                name=title,
                value=content,
                inline=True,
            )

        if self.statistics.manga:
            title, content = CStatisticsUnion.create(self.statistics).embed_string(
                "manga"
            )
            embed.add_field(
                name=title,
                value=content,
                inline=True,
            )

        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.info(
                    f"Cannot send message -> {str(channel.id)} : {self.name} {e}"
                )
        else:
            return embed


class CListActivity(ListActivity):

    username = None
    sent_message = None

    @staticmethod
    def create(obj: ListActivity, username: str = None) -> "CListActivity":
        obj.__class__ = CListActivity

        if username:
            obj.username = username

        obj.sent_message = None

        return obj

    @staticmethod
    def get_score_color(user: CUser, score: int) -> Tuple[int, int, int]:
        amount = 5
        colors = user.get_color_list(amount)
        colors.reverse()

        delta = 100 / amount

        for i in range(amount):
            range_min = 0 + i * delta
            range_max = range_min + delta

            if in_range(score, range_min, range_max):
                return colors[i]

        return colors[0]

    async def get_list(self, anilist: AsyncClient) -> Dict[User, MediaList]:

        if not self.username:
            return None, None

        user = await anilist.get_user(self.username)
        if not user:
            return None, None

        listitem = await anilist.get_list_item(self.username, self.media.id)
        return user, listitem

    @staticmethod
    async def send_embed(
        item: "CListActivity",
        anilist: AsyncClient,
        channel: discord.TextChannel = None,
        filter_adult: bool = True,
        activity=None,
    ) -> Optional[discord.Embed]:

        item_idx = -1
        if activity:
            item_idx = activity.feed.entries.index(item)

        user, listitem = await item.get_list(anilist)
        if not user or not listitem:
            return None

        user = CUser.create(user)
        listitem: MediaList

        if channel:
            channels = await database.channel_get()
            matching = [ch for ch in channels if int(ch["channel"]) == channel.id]
            if len(matching):
                ch = matching[0]

                # progress
                if listitem.status in ["CURRENT", "REPEATING", "COMPLETED"]:
                    if ch["list_block_progress"]:
                        return None
                elif listitem.status == "PAUSED":
                    if ch["list_block_paused"]:
                        return None
                elif listitem.status == "DROPPED":
                    if ch["list_block_dropped"]:
                        return None
                elif listitem.status == "PLANNING":
                    if ch["list_block_planning"]:
                        return None

        color = discord.Color(0x000000)

        is_manga = isinstance(item.media, Manga)

        merged = False
        if item.status and item.status.progress:
            progress = "{}. {}".format(
                item.status,
                "\n Score ⭐: {}".format(listitem.score)
                if hasattr(listitem, "score") > 0 and listitem.status == "COMPLETED"
                else "",
            )

            if "-" in str(item.status):
                merged = True
        else:
            if is_manga:
                progress = "Total {} chapters. {}{}".format(
                    str(item.media.chapters)
                    if hasattr(item.media, "chapters")
                    else "???",
                    f"{str(item.media.volumes)} volumes. "
                    if hasattr(item.media, "volumes")
                    else "",
                    "\n Score ⭐: {}".format(listitem.score)
                    if hasattr(listitem, "score") > 0 and listitem.status == "COMPLETED"
                    else "",
                )
            else:
                progress = "Total {} episodes. {}".format(
                    str(item.media.episodes)
                    if hasattr(item.media, "episodes")
                    else "???",
                    "\n Score ⭐: {}".format(listitem.score)
                    if hasattr(listitem, "score") > 0 and listitem.status == "COMPLETED"
                    else "",
                )

        status = ""
        if listitem.status == "CURRENT":
            if listitem.progress <= 1:
                progress = f"Just started {'reading' if is_manga else 'watching'}."

            status = "Reading" if is_manga else "Watching"
            color = color_done

        elif listitem.status == "REPEATING":
            status = f"Re{'reading' if is_manga else 'watching'}"
            color = color_done

        elif listitem.status == "COMPLETED":
            if hasattr(listitem, "repeat") > 0:
                status = f"Finished Re{'reading' if is_manga else 'watching'}"
            else:
                status = str(item.status)

            if hasattr(listitem, "score"):
                r, g, b = CListActivity.get_score_color(user, listitem.score)
                color = discord.Color.from_rgb(r, g, b)
            else:
                color = color_main

        elif listitem.status == "PAUSED":
            status = str(item.status)
            color = color_warn

        elif listitem.status == "DROPPED":
            status = str(item.status)

            if hasattr(listitem, "score") > 0:
                r, g, b = CListActivity.get_score_color(user, listitem.score)
                color = discord.Color.from_rgb(r, g, b)
            else:
                color = color_errr

        elif listitem.status == "PLANNING":
            if hasattr(listitem, "repeat") > 0:
                status = f"Planning to {'Read' if is_manga else 'Watch'} Again"
            else:
                status = str(item.status)

            if is_manga:
                if hasattr(item.media, "chapters"):
                    progress = f"Total chapters: {str(item.media.chapters)} chapters - {str(item.media.volumes) if hasattr(item.media, 'volumes') else '???'} volumes"
                else:
                    progress = "Total chapters: Not Available"
            else:
                progress = f"Total episodes: {str(item.media.episodes) if hasattr(item.media, 'episodes') else 'Not Available'}"
            color = color_main

        else:
            status = str(item.status)

        embed = discord.Embed(
            title=item.media.title.romaji,
            url=item.media.url,
            description=(
                (item.media.title.english + "\n")
                if hasattr(item.media.title, "english")
                else (item.media.title.native + "\n")
            )
            + (f"Updated <t:{item.date.get_timestamp()}:R>"),
            color=color,
        )
        embed.add_field(
            name=status,
            value=progress,
            inline=False,
        )

        if listitem.status == "COMPLETED" or listitem.status == "PLANNING":
            if is_manga:
                cobj = CManga.create(item.media)
            else:
                cobj = CAnime.create(item.media)

            cobj: Union[CManga, CAnime]
            stat_embed = await cobj.send_embed()

            embed.add_field(
                name=stat_embed.fields[0].name,
                value=stat_embed.fields[0].value,
                inline=False,
            )

            if (
                hasattr(item.media, "is_adult") and item.media.is_adult
            ) and filter_adult:
                embed.set_image(
                    url=f"https://mitsu.0x16c3.com/filter/media/{item.media.id}"
                )
            else:
                embed.set_image(url=f"https://img.anili.st/media/{item.media.id}")
        else:
            if (
                hasattr(item.media, "is_adult") and item.media.is_adult
            ) and filter_adult:
                embed.set_thumbnail(
                    url=f"https://mitsu.0x16c3.com/filter/cover/{'MANGA' if is_manga else 'ANIME'}-{str(item.media.id)}"
                )
            else:
                embed.set_thumbnail(url=item.media.cover.large)

        embed.set_footer(
            text=f"{'Manga' if is_manga else 'Anime'} list of {item.username}",
            icon_url=user.image.medium,
        )

        if channel:
            try:
                if activity:
                    for idx, feed in enumerate(activity.feed.entries_processed):
                        feed: "CListActivity"

                        if (
                            not feed.sent_message
                            or feed.media.id != item.media.id
                            or feed.status.string
                            not in [
                                "WATCHED EPISODE",
                                "REWATCHED EPISODE",
                                "READ CHAPTER",
                                "REREAD CHAPTER",
                            ]
                        ):
                            continue
                        else:
                            if not merged:
                                pass
                            else:
                                try:
                                    await feed.sent_message.delete()
                                except Exception as e:
                                    logger.info(
                                        f"Cannot remove message -> {str(channel.id)} : {item.username}\n{e}"
                                    )

                    item.sent_message = await channel.send(embed=embed)
                    activity.feed.entries[item_idx] = item

                    return "List[CListActivity]", activity.feed.entries, item

                else:
                    item.sent_message = await channel.send(embed=embed)
                    activity.feed.entries[item_idx] = item

                    return "List[CListActivity]", activity.feed.entries, item

            except Exception as e:
                logger.debug(
                    f"Cannot send message -> {str(channel.id)} : {item.username} {e}"
                )
        else:
            return embed


class CTextActivity(TextActivity):

    username = None

    @staticmethod
    def create(obj: TextActivity, username) -> "CTextActivity":
        obj.__class__ = CTextActivity
        obj.username = username

        return obj

    @staticmethod
    async def send_embed(
        item: "CTextActivity",
        anilist: AsyncClient,
        channel: discord.TextChannel = None,
        **kwargs,
    ) -> Optional[discord.Embed]:

        # user == sender
        if not hasattr(item, "user"):
            return None

        user = await anilist.get_user(item.user.name)
        if not user:
            return None

        user = CUser.create(user)
        item.user = user

        if hasattr(item, "recipient"):
            received = True

            recipient = await anilist.get_user(item.recipient.name)
            if not recipient:
                return None

            recipient = CUser.create(recipient)
            item.recipient = recipient

        color = discord.Color.from_rgb(
            user.profile_color[0], user.profile_color[1], user.profile_color[2]
        )

        embed = discord.Embed(
            title=f"New post on {item.recipient.name if hasattr(item, 'recipient') else item.username}'s profile!",
            url=item.url if hasattr(item, "url") else "https://anilist.co/",
            description=f"Sent <t:{item.date.get_timestamp()}:R>",
            color=color,
        )

        regex = re.findall(
            r"(img[0-9]+\()(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)(\))$",
            item.text,
        )
        count = 0
        for i in regex:
            count += 1

            if count > 4:
                item.text = item.text.replace("".join(i), i[1])
            else:
                item.text = item.text.replace("".join(i), "")
                embed.set_image(url=i[1])

        if hasattr(item, "text"):
            embed.add_field(
                name=f"Sent by {item.user.name}",
                value=item.text,
                inline=False,
            )
        else:
            embed.add_field(
                name="ERROR",
                value="`An error occured fetching this activity.`",
                inline=False,
            )

        embed.set_thumbnail(
            url=item.recipient.image.large
            if hasattr(item, "recipient")
            else item.user.image.large
        )
        embed.set_footer(
            text=f"Status activity of {item.username}",
            icon_url=user.image.medium,
        )

        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.info(
                    f"Cannot send message -> {str(channel.id)} : {item.username} {e}"
                )
        else:
            return embed


class CStatisticsUnion(StatisticsUnion):
    @staticmethod
    def create(obj: StatisticsUnion):
        obj.__class__ = CStatisticsUnion
        return obj

    @staticmethod
    def status(items: list, status: str) -> Dict[str, int]:
        res = [x for x in items if x[0] == status]

        if len(res):
            return res[0]
        else:
            return ["", 0]

    def embed_string(self, content_type: str = "anime") -> Optional[Dict[str, str]]:
        title: List[str] = []
        content: List[str] = []

        if content_type == "anime":
            title.append(f"**Anime Statistics**")
            title.append(
                f"> `Total Entries: {self.anime.count if hasattr(self.anime, 'count') else '-'}`"
            )
            title.append(
                f"> `Total Episodes: {self.anime.episodes_watched if hasattr(self.anime, 'episodes_watched') else '-'}`"
            )
            title.append(
                f"> `Hours Watched: {round(self.anime.minutes_watched / 60, 1) if hasattr(self.anime, 'minutes_watched') else '-'}`"
            )

            if hasattr(self.anime, "statuses"):
                len_status = []
                for e in ["CURRENT", "COMPLETED", "PAUSED", "DROPPED", "PLANNING"]:
                    len_status.append(str(self.status(self.anime.statuses, e)[1]))

                longest = max((len(x) for x in len_status))

                compact = False
                if longest >= 5:
                    compact = True

                content.append(
                    f"``` {'Watching  ' if not compact else ''}[📺]: {str(len_status[0]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Completed ' if not compact else ''}[✔️]: {str(len_status[1]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Paused    ' if not compact else ''}[🛑]: {str(len_status[2]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Dropped   ' if not compact else ''}[🗑️]: {str(len_status[3]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Planned   ' if not compact else ''}[📆]: {str(len_status[4]).rjust(longest, '0')} ```"
                )
            else:
                content.append(f"``` Watching  [📺]: - ")
                content.append(f" Completed [✔️]: - ")
                content.append(f" Paused    [🛑]: - ")
                content.append(f" Dropped   [🗑️]: - ")
                content.append(f" Planned   [📆]: - ```")

        elif content_type == "manga":
            title.append(f"**Manga Statistics**")
            title.append(
                f"> `Total Entries: {self.manga.count if hasattr(self.manga, 'count') else '-'}`"
            )
            title.append(
                f"> `Total Volumes: {self.manga.volumes_read if hasattr(self.manga, 'volumes_read') else '-'}`"
            )
            title.append(
                f"> `Total Chapters: {self.manga.chapters_read if hasattr(self.manga, 'chapters_read') else '-'}`"
            )

            if hasattr(self.manga, "statuses"):
                len_status = []
                for e in ["CURRENT", "COMPLETED", "PAUSED", "DROPPED", "PLANNING"]:
                    len_status.append(str(self.status(self.manga.statuses, e)[1]))

                longest = max((len(x) for x in len_status))

                compact = False
                if longest >= 5:
                    compact = True

                content.append(
                    f"``` {'Reading   ' if not compact else ''}[📖]: {str(len_status[0]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Completed ' if not compact else ''}[✔️]: {str(len_status[1]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Paused    ' if not compact else ''}[🛑]: {str(len_status[2]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Dropped   ' if not compact else ''}[🗑️]: {str(len_status[3]).rjust(longest, '0')} "
                )
                content.append(
                    f" {'Planned   ' if not compact else ''}[📆]: {str(len_status[4]).rjust(longest, '0')} ```"
                )
            else:
                content.append(f"``` Reading   [📖]: - ")
                content.append(f" Completed [✔️]: - ")
                content.append(f" Paused    [🛑]: - ")
                content.append(f" Dropped   [🗑️]: - ")
                content.append(f" Planned   [📆]: - ```")
        else:
            raise TypeError("content_type must be either anime or manga")

        return "\n".join(title), "\n".join(content)


class CFavouritesUnion(FavouritesUnion):
    @staticmethod
    def create(obj: FavouritesUnion):
        obj.__class__ = CFavouritesUnion
        return obj

    def embed_string(self, items: List) -> Dict[str, str]:
        if not len(items):
            return None

        if isinstance(items[0], Anime):
            return None
        elif isinstance(items[0], Manga):
            return None
        elif isinstance(items[0], Character):
            return None
        elif isinstance(items[0], Staff):
            return None
        elif isinstance(items[0], Studio):
            return None
        else:
            raise TypeError("invalid item type in items")
