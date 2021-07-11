import ast
import discord
import json

import math

from discord.ext import commands
from tinydb.database import TinyDB
from tinydb.queries import where

from cogs.controller import (
    Controller,
    Feed,
    AnimeFeed,
)
from cogs.api.types import (
    CAnime,
    CManga,
    CUser,
    CListActivity,
    CFavouritesUnion,
    CStatisticsUnion,
)
from cogs.api.database import Database, database
from cogs.utils import *


class Eval(commands.Cog):
    def __init__(self, client):
        self.client = client

    def insert_returns(self, body):
        # insert return stmt if the last expression is a expression statement
        if isinstance(body[-1], ast.Expr):
            body[-1] = ast.Return(body[-1].value)
            ast.fix_missing_locations(body[-1])

        # for if statements, we insert returns into the body and the orelse
        if isinstance(body[-1], ast.If):
            insert_returns(body[-1].body)
            insert_returns(body[-1].orelse)

        # for with blocks, again we insert returns into the body
        if isinstance(body[-1], ast.With):
            insert_returns(body[-1].body)

    @commands.command()
    async def eval(self, ctx, *, cmd):

        # modify your owner ids here
        if (
            str(ctx.author.id) != "346941434202685442"
            and str(ctx.author.id) != "611635076769513507"
        ):
            return

        """Evaluates input.
        Input is interpreted as newline seperated statements.
        If the last statement is an expression, that is the return value.
        Usable globals:
        - `client`: the bot instance
        - `discord`: the discord module
        - `commands`: the discord.ext.commands module
        - `ctx`: the invokation context
        - `json`: json
        - `__import__`: the builtin `__import__` function
        Such that `>eval 1 + 1` gives `2` as the result.
        The following invokation will cause the bot to send the text '9'
        to the channel of invokation and return '3' as the result of evaluating
        >eval ```
        a = 1 + 2
        b = a * 2
        await ctx.send(a + b)
        a
        ```
        """
        fn_name = "_eval_expr"

        cmd = cmd.strip("` ")

        # add a layer of indentation
        cmd = "\n".join(f"    {i}" for i in cmd.splitlines())

        # wrap in async def body
        body = f"async def {fn_name}():\n{cmd}"

        parsed = ast.parse(body)
        body = parsed.body[0].body

        self.insert_returns(body)

        env = {
            "client": self.client,
            "discord": discord,
            "commands": commands,
            "ctx": ctx,
            "json": json,
            "Controller": Controller,
            "Feed": Feed,
            "AnimeFeed": AnimeFeed,
            "Database": Database,
            "database": database,
            "TinyDB": TinyDB,
            "where": where,
            "anilist": anilist,
            "CAnime": CAnime,
            "CManga": CManga,
            "CUser": CUser,
            "CListActivity": CListActivity,
            "CFavouritesUnion": CFavouritesUnion,
            "CStatisticsUnion": CStatisticsUnion,
            "color_main": color_main,
            "color_done": color_done,
            "color_warn": color_warn,
            "color_errr": color_errr,
            "math": math,
            "__import__": __import__,
        }
        exec(compile(parsed, filename="<ast>", mode="exec"), env)

        result = await eval(f"{fn_name}()", env)
        # await ctx.send(result)


def setup(client):
    client.add_cog(Eval(client))
