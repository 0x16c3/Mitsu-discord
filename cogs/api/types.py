# discord imports
import discord
import asyncio

# utilities
import math
from PIL import Image
import urllib.request, io
from typing import Optional, Tuple
from ..utils import *

# anilist
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
    score,
)


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

    @staticmethod
    def create(obj: ListActivity, username: str = None):
        obj.__class__ = CListActivity

        if username:
            obj.username = username

        return obj

    @staticmethod
    def get_score_color(user: CUser, score: int) -> Tuple[int, int, int]:
        amount = 5
        colors = user.get_color_list(amount)

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
        item: "CListActivity", anilist: AsyncClient, channel: discord.TextChannel = None
    ) -> Optional[discord.Embed]:

        user, listitem = await item.get_list(anilist)
        if not user or not listitem:
            return None

        user = CUser.create(user)
        listitem: MediaList

        color = discord.Color(0x000000)

        is_manga = isinstance(item.media, Manga)

        if item.status and item.status.progress:
            progress = "{}. {}".format(
                str(item.status)
                if isinstance(item.status.progress, int)
                else " - ".join(str(i) for i in item.status.progress),
                "\n Score ⭐: {}".format(listitem.score)
                if listitem.score > 0 and listitem.status == "COMPLETED"
                else "",
            )
        else:
            progress = "Total {} episodes. {}".format(
                str(item.media.episodes) if hasattr(item.media, "episodes") else "???",
                "\n Score ⭐: {}".format(listitem.score)
                if listitem.score > 0 and listitem.status == "COMPLETED"
                else "",
            )

        status = ""
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
            else:
                status = str(item.status)

            if listitem.score > 0:
                r, g, b = CListActivity.get_score_color(user, listitem.score)
                color = discord.Color.from_rgb(r, g, b)
            else:
                color = color_main

        elif listitem.status == "PAUSED":
            status = str(item.status)
            color = color_warn

        elif listitem.status == "DROPPED":
            status = str(item.status)

            if listitem.score > 0:
                r, g, b = CListActivity.get_score_color(user, listitem.score)
                color = discord.Color.from_rgb(r, g, b)
            else:
                color = color_errr

        elif listitem.status == "PLANNING":
            if listitem.repeat > 0:
                status = f"Planning to {'Read' if is_manga else 'Watch'} Again"
            else:
                status = str(item.status)

            if is_manga:
                if item.media.chapters:
                    progress = f"Total chapters: {str(item.media.chapters)} chapters - {str(item.media.volumes)} volumes"
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
            description=item.media.title.english
            if hasattr(item.media.title, "english")
            else item.media.title.native,
            color=color,
        )
        embed.add_field(
            name=status,
            value=progress,
            inline=False,
        )

        if listitem.status == "COMPLETED" or listitem.status == "PLANNING":
            ranking = None
            if hasattr(item.media, "rankings"):
                ranking = item.media.rankings[0]
            embed.add_field(
                name="Stats 🧮",
                value=(
                    f"{'Manga' if is_manga else 'Anime'}\n"
                    + (
                        f"Premiered {item.media.season.name.title()} {item.media.season.year}\n"
                        if item.media.start_date
                        else "Not Premiered Yet\n"
                    )
                    + (
                        f"> Score ⭐: `{string(item.media.score.mean)}`\n"
                        if hasattr(item.media.score, "mean")
                        else ""
                    )
                    + (
                        f"> Rank 📈: `#{string(ranking.rank)} on {ranking.format}({str(ranking.year) if not ranking.all_time else 'All time'})`\n"
                        if ranking
                        else ""
                    )
                    + (
                        f"> Popularity 📈: `#{string(item.media.popularity)}`\n"
                        if hasattr(item.media, "popularity")
                        else ""
                    )
                    + f"Description 📔: \n> {string(strip_tags(item.media.description[:128])) + ('...' if len(string(strip_tags(item.media.description))) > 128 else '')}"
                ),
                inline=False,
            )
            embed.set_image(url=f"https://img.anili.st/media/{item.media.id}")
        else:
            embed.set_thumbnail(url=item.media.cover.large)

        embed.set_footer(
            text=f"{'Manga' if is_manga else 'Anime'} list of {item.username}",
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