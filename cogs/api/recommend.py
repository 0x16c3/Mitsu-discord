# discord imports
import discord
from discord.ext import commands
import asyncio

# utilities
from ..utils import anilist
from .types import CUser, CAnime
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Relation:
    media_id: int
    mean_score: float
    tags: List[str]
    genres: List[str]
    popularity: int
    episodes: int

    user_score: float


class Recommender:
    def __init__(self, user: CUser) -> None:
        self.user = user

    @staticmethod
    async def create(username: str) -> "Recommender":
        pages, entries = await anilist.get(username, "anime_list", limit=50)

        for page in range(2, pages.last + 1):
            print(page)
            _, entries_sub = await anilist.get(
                username, "anime_list", page=page, limit=50
            )
            entries.extend(entries_sub)

        relations: List[Relation] = []
        genre_matrix: Dict[str, int] = {}
        tag_matrix: Dict[str, int] = {}

        for entry in entries:
            if not hasattr(entry, "score"):
                continue

            media = entry.media
            for genre in media.genres:
                if genre not in genre_matrix:
                    genre_matrix[genre] = 1
                    continue

                genre_matrix[genre] += 1
            for tag in media.tags:
                if tag not in tag_matrix:
                    tag_matrix[tag] = 1
                    continue

                tag_matrix[tag] += 1

            relations.append(
                Relation(
                    media.id,
                    media.score.mean,
                    media.tags,
                    media.genres,
                    media.popularity,
                    media.episodes,
                    entry.score,
                )
            )

        genre_matrix: List[Tuple[str, int]] = sorted(
            genre_matrix.items(), key=lambda v: v[1]
        )
        genre_matrix.reverse()

        tag_matrix: List[Tuple[str, int]] = sorted(
            tag_matrix.items(), key=lambda v: v[1]
        )
        tag_matrix.reverse()
