# scroll

Scroll is full-featured IRC bot that carries a **PENIS PUMP** & will brighten up all the mundane chats in your lame IRC channels with some colorful IRC artwork! Designed to be extremely stable, this bot is sure to stay rock hard & handle itself quite well!

All of the IRC art is loaded directly from the [ircart](https://git.supernets.org/ircart/ircart) central repository, which means that anytime the repository is updated with new art, you can simply `.ascii sync` & then be able to pump the latest art packs!

Designed to be portable, there is no API key needed, no local art files needed, & no reason to not setup scroll in your channel(s) today!

## Dependencies
* [python](https://www.python.org/)
* [aiohttp](https://pypi.org/project/aiohttp/) *(`pip install aiohttp`)*
* [chardet](https://pypi.org/project/chardet/) *(`pip install chardet`)*

## Commands
| Command                                | Description                                                |
| -------------------------------------- | ---------------------------------------------------------- |
| `@scroll`                              | information about scroll                                   |
| `.ascii <name>`                        | play the \<name> art file                                  |
| `.ascii dirs`                          | list of art directories                                    |
| `.ascii flag <name> <reason>`          | flag bad art for review *(saved to flagged.txt)*           |
| `.ascii list`                          | list of art filenames                                      |
| `.ascii random [dir\|query]`           | play random art, optionally from a [dir] or [query]        |
| `.ascii search <query>`                | search art files that match \<query>                       |
| `.ascii settings [<setting> <option>]` | view or change settings                                    |
| `.ascii stop`                          | stop playing art                                           |
| `.ascii sync`                          | sync the ascii database to pump the newest art             |

**NOTE**: You can do `.ascii help` to play the [help.txt](https://git.supernets.org/ircart/ircart/src/branch/master/ircart/doc/help.txt) file in your channel.

**NOTE**: The flag, sync & settings commands are admin only! `admin` is a *nick!user@host* mask defined in [scroll.py](https://git.supernets.org/ircart/scroll/src/branch/master/scroll.py)

## Settings
| Setting               | Type         | Description                                                                                  |
| --------------------- | ------------ | -------------------------------------------------------------------------------------------- |
| `flood`               | int or float | delay between each command                                                                   |
| `ignore`              | str          | directories to ignore in `.ascii random` *(comma seperated list, no spaces)*                 |
| `linelen`             | int          | server line limit in bytes, including the trailing `\r\n` *(art lines are trimmed to fit)*   |
| `lines`               | int          | max lines outside of #scroll                                                                 |
| `msg`                 | int or float | delay between each message sent                                                              |
| `results`             | int          | max results to return in `.ascii search`                                                     |

## Preview

![](.screens/preview1.png)

![](.screens/preview2.png)

Come pump with us in **#scroll** on [irc.supernets.org](ircs://irc.supernets.org)

___

###### Mirrors: [SuperNETs](https://git.supernets.org/ircart/scroll) • [GitHub](https://github.com/ircart/scroll) • [GitLab](https://gitlab.com/ircart/scroll) • [Codeberg](https://codeberg.org/ircart/scroll)
