<div>
	<img
		src="img/mitsu.png"
		alt="mitsu"
		width="100px"
		height="100px"
	/>
</div>

# Mitsu

[![Invite Mitsu](https://img.shields.io/badge/Invite-Mitsu-000000?style=flat&colorA=000000&colorB=5191F5)](https://discord.com/api/oauth2/authorize?client_id=862650879688441857&permissions=537259008&scope=bot%20applications.commands)

### Usage

|                                         |                                                           |
| --------------------------------------- | --------------------------------------------------------- |
| **Helper functions**                    |                                                           |
| `mitsu`                                 | `meta information`                                        |
| .                                       |                                                           |
| **Commands**                            |                                                           |
| `/activity <username>`                  | `setup AniList feed in current channel (Manage Webhooks)` |
| `/edit`                                 | `edit active feeds in current channel (Manage Webhooks)`  |
| `/active [scope]`                       | `get active feeds in the specified scope`                 |
| `/profile <username> [send-message]`    | `get AniList profile of specified user`                   |
| `/search <type (Anime, Manga)> <query>` | `search anime or manga`                                   |

### Running & configuration

- Install requirements.
  `pip install -r requirements.txt`

- Setup Token & Slash Command Test Guild

  1. Create and enter the directory `tmp`.
  2. Create a text file and name it `token.txt`.
  3. Paste your Discord bot token into the file.

  For developers:
  Set `SLASH_TEST_GUILD` as your test server's if you're going to add or edit commands.
  Otherwise you'd need to wait at least a couple of hours for the commands to sync.

  For further configuration, check out `tmp/config.ini`

- Run the main script.
  `py main.py [--info|--debug]`

> Please read [AniList's Rate Limiting Policy](https://anilist.gitbook.io/anilist-apiv2-docs/overview/rate-limiting)
> And configure your `INTERVAL` accordingly.

> Oh and one more thing. Please update my fork of python-anilist before you run the bot.
> I tend to push a lot of updates :S
