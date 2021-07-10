import discord
import asyncio

from typing import Optional
from ..utils import *

from anilist import AsyncClient
from anilist.types import (
    Anime,
    Manga,
    ListActivity,
    User,
    FavouritesUnion,
    StatisticsUnion,
    Character,
    Staff,
    Studio,
    Statistic,
    MediaList,
    Title,
)

from PIL import Image, ImageDraw, ImageFont
import urllib.request, io


class CAnime(Anime):
    def create(obj: Anime):
        obj.__class__ = CAnime
        return obj

    async def send_embed(
        self,
        channel: discord.TextChannel = None,
    ) -> Optional[discord.Embed]:
        pass


class CManga(Manga):
    def create(obj: Manga):
        obj.__class__ = CManga
        return obj

    async def send_embed(
        self,
        channel: discord.TextChannel = None,
    ) -> Optional[discord.Embed]:
        pass


class CUser(User):
    @staticmethod
    def create(obj: User):
        obj.__class__ = CUser
        return obj

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
        self,
        channel: discord.TextChannel = None,
    ) -> Optional[discord.Embed]:
        loop = asyncio.get_event_loop()

        estimate = await loop.run_in_executor(None, self.get_picture_color)

        color = discord.Color.from_rgb(estimate[0], estimate[1], estimate[2])

        embed = discord.Embed(
            title=f"{self.name}'s Profile",
            url=self.url,
            description=strip_tags(self.about)
            if hasattr(self, "about")
            else "No biography yet.",
            color=color,
        )
        embed.set_thumbnail(url=self.image.large)

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
            except:
                logger.info(f"Cannot send message -> {str(channel.id)} : {self.name}")
        else:
            return embed


class CListActivity(ListActivity):

    username = None

    @staticmethod
    def create(obj: ListActivity, username: str = None):
        obj.__class__ = CListActivity

        if username:
            obj.username = username

        return obj

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
        item: "CListActivity", anilist: AsyncClient, channel: discord.TextChannel = None
    ) -> Optional[discord.Embed]:

        user, listitem = await item.get_list(anilist)
        if not user or not listitem:
            return None

        user: User
        listitem: MediaList

        color = discord.Color(0x000000)

        is_manga = isinstance(item.media, Manga)

        status = ""
        progress = "{} {}. {}".format(
            str(item.status.progress)
            if isinstance(item.status.progress, int)
            else " - ".join(str(i) for i in item.status.progress),
            "chapters" if is_manga else "episodes",
            "\n Score ⭐: {}".format(listitem.score)
            if listitem.score > 0 and item.status == "COMPLETED"
            else "",
        )

        if listitem.status == "CURRENT":
            if listitem.progress == 0:
                progress = f"Just started {'reading' if is_manga else 'watching'}."

            status = "Reading" if is_manga else "Watching"
            color = color_done

        elif listitem.status == "REPEATING":
            status = f"Re{'reading' if is_manga else 'watching'}"
            color = color_done

        elif listitem.status == "COMPLETED":
            if listitem.repeat > 0:
                status = f"Finished Re{'reading' if is_manga else 'watching'}"

            color = color_main

        elif listitem.status == "PAUSED":
            color = color_warn

        elif listitem.status == "DROPPED":
            color = color_errr

        elif listitem.status == "PLANNING":
            if listitem.repeat > 0:
                status.status = f"Planning to {'Read' if is_manga else 'Watch'} Again"

            if is_manga:
                if item.media.chapters:
                    progress = f"Total chapters: {str(item.media.chapters)} chapters - {str(item.media.volumes)} volumes"
                else:
                    progress = "Total chapters: Not Available"
            else:
                progress = f"Total episodes: {str(item.media.episodes) if item.media.episodes else 'Not Available'}"
            color = color_main

        embed = discord.Embed(
            title=item.media.title.romaji,
            url=item.media.url,
            description=item.media.title.english,
            color=color,
        )
        embed.set_thumbnail(url=item.media.cover.large)
        embed.add_field(
            name=status,
            value=progress,
            inline=False,
        )

        if listitem.status == "COMPLETED" or listitem.status == "PLANNING":
            ranking = item.media.rankings[0]
            embed.add_field(
                name="Stats 🧮",
                value=(
                    f"{'Manga' if is_manga else 'Anime'}\n"
                    + (
                        f"Premiered in {item.media.start_date}\n"
                        if item.media.start_date
                        else "Not Premiered Yet\n"
                    )
                    + f"> Score ⭐: `{string(item.media.score.average)}`\n"
                    + f"> Rank 📈: `#{string(ranking.rank)} on {ranking.format}({str(ranking.year) if not ranking.all_time else 'All time'})` \n> Popularity 📈: `#{string(item.media.popularity)}`\n"
                    + f"Description 📔: \n> {string(item.media.description)[:512] + ('...' if len(string(item.media.description)) > 512 else '')}"
                ),
                inline=False,
            )

        embed.set_footer(
            text=f"{'Manga' if is_manga else 'Anime'} list of {item.username}",
            icon_url=user.image.medium,
        )

        if channel:
            try:
                await channel.send(embed=embed)
            except:
                logger.info(
                    f"Cannot send message -> {str(channel.id)} : {item.username}"
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
            title.append(f"> `Total Entries: {self.anime.count}`")
            title.append(f"> `Total Episodes: {self.anime.episodes_watched}`")
            title.append(
                f"> `Hours Watched: {round(self.anime.minutes_watched / 60, 1)}`"
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
            title.append(f"> `Total Entries: {self.manga.count}`")
            title.append(f"> `Total Volumes: {self.manga.volumes_read}`")
            title.append(f"> `Total Chapters: {self.manga.chapters_read}`")

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