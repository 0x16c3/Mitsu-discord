import discord
import json
import os
from datetime import datetime
from typing import Dict, List
import configparser

# anilist
import anilist

"""
    LOGGING
"""


class Log:
    def __init__(self, debug: bool = False, info: bool = False) -> None:
        self._debug = debug
        self._info = info

    def debug(self, msg):
        if self._debug:
            print("DEBUG: " + msg)

    def info(self, msg):
        if self._info or self._debug:
            print("INFO: " + msg)

    def print(self, msg):
        print("LOG: " + msg)


logger = Log()
""""""


"""
    COLORS
"""
color_main = discord.Color(0xF5F5F5)
color_done = discord.Color(0x00FFFF)
color_warn = discord.Color(0xFFFF00)
color_errr = discord.Color(0xFF0000)
""""""

"""
    FUNCTIONS
"""


def date_format(time) -> str:

    if "+" in time:
        time = time.split("+")[0]
    elif "-" in time:
        time = time.split("-")[0]

    date_format = "%Y-%m-%dT%H:%M:%S"
    date = datetime.strptime(time, date_format)

    if date.date() == datetime.today().date():
        return "Today"

    return date.strftime("%d/%m/%Y")


def string(obj) -> str:
    if not obj:
        return "Not Available"

    if isinstance(obj, str):
        return obj

    return str(obj)


from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType
from .client import client


def get_all_guild_ids() -> List[int]:

    ids = []

    for guild in client.guilds:
        guild: discord.Guild
        ids.append(guild.id)

    return ids


def get_all_permissions() -> Dict[int, list]:

    guilds = {}

    for guild in client.guilds:
        guild: discord.Guild

        permissions = []

        for role in guild.roles:
            role: discord.Role

            if role.permissions.manage_webhooks:
                permissions.append(
                    create_permission(role.id, SlashCommandPermissionType.ROLE, True)
                )
                continue

            permissions.append(
                create_permission(role.id, SlashCommandPermissionType.ROLE, False)
            )

        guilds[guild.id] = permissions

    return guilds


# https://stackoverflow.com/a/925630
from io import StringIO
from html.parser import HTMLParser


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


import math
from typing import Tuple


def in_range(value, low, hi) -> bool:
    if low <= value <= hi:
        return True
    return False


def rgb_to_hsv(r, g, b):
    r = float(r)
    g = float(g)
    b = float(b)
    high = max(r, g, b)
    low = min(r, g, b)
    h, s, v = high, high, high

    d = high - low
    s = 0 if high == 0 else d / high

    if high == low:
        h = 0.0
    else:
        h = {
            r: (g - b) / d + (6 if g < b else 0),
            g: (b - r) / d + 2,
            b: (r - g) / d + 4,
        }[high]
        h /= 6

    return h, s, v


def hsv_to_rgb(h, s, v):
    i = math.floor(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    r, g, b = [
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    ][int(i % 6)]

    return round(r), round(g), round(b)


def rotate_hue(color: Tuple[int, int, int], angle) -> Tuple[int, int, int]:
    h, s, v = rgb_to_hsv(color[0], color[1], color[2])
    h = math.fmod(h + angle / 360.0, 1.0)

    return hsv_to_rgb(h, s, v)


""""""

"""
    CONFIG
"""
cfgparser = configparser.ConfigParser()

if not os.path.isfile("tmp/config.ini"):
    fp = open("tmp/config.ini", "w")
    fp.write("[DEFAULT]\n")
    fp.write("; interval for recieving list updates\n")
    fp.write("INTERVAL = 60\n")
    fp.write("; maximum list items that a RssFeed object can contain\n")
    fp.write("MEMORY_LIMIT = 25\n")
    fp.close()

cfgparser.read("tmp/config.ini", encoding="utf-8-sig")
config = cfgparser["DEFAULT"]

logger.print(
    f"LOADED CONFIG:\n"
    f'  INTERVAL = {config["INTERVAL"]}\n'
    f'  MEMORY_LIMIT = {config["MEMORY_LIMIT"]}\n'
)
""""""

"""
    JIKAN
"""
anilist = anilist.AsyncClient()
""""""