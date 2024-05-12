import textwrap
from collections.abc import Mapping
from copy import deepcopy
from difflib import get_close_matches
from typing import Any

from discord import Embed, utils
from discord.ext import commands

from kolkra_ng.context import KolkraContext
from kolkra_ng.embeds import InfoEmbed, SplitEmbed
from kolkra_ng.views.confirm import Confirm
from kolkra_ng.views.pager import Pager, group_embeds


class KolkraHelp(commands.HelpCommand):
    """Shows this message."""

    context: KolkraContext  # pyright: ignore [reportIncompatibleVariableOverride]

    def base_embed(self, **kwargs) -> Embed:
        return InfoEmbed(**kwargs).set_footer(
            text=f"Type {self.context.clean_prefix}{self.invoked_with} [command|category] for more information."
        )

    def command_display(
        self, command: commands.Command, include_description: bool = True
    ) -> str:
        name = "|".join([command.name, *command.aliases])
        description = (
            textwrap.shorten(command.short_doc, 1024 - len(name))
            or "no description found"
        )
        return f"{name}{': ' + description if include_description else ''}"

    def command_flags(self, command: commands.Command) -> list[str] | None:
        flags: dict[str, commands.Flag] = {}
        for param in command.params.values():
            if isinstance(param.annotation, commands.flags.FlagsMeta):
                flags.update(
                    param.annotation.get_flags()  # pyright: ignore [reportAttributeAccessIssue]
                )
        if not flags:
            return None
        formatted_flags = []
        for name, flag in flags.items():
            if flag.description == utils.MISSING:
                flag.description = "No description provided"
            name_and_aliases = "|".join([name, *flag.aliases])
            default = f" (default: {flag.default})" if flag.default else ""
            formatted_flags.append(
                f"- {name_and_aliases}{' [positional]' if flag.positional else ''}: {flag.description}{default}"
            )
        return formatted_flags

    async def command_embed(self, command: commands.Command) -> Embed:
        embed = self.base_embed(title=command.qualified_name, description=command.help)

        embed.add_field(
            name="Usage",
            value=self.get_command_signature(command),
        )
        try:
            can_run, err = (
                await command.can_run(self.context),
                "no error raised",
            )
        except commands.CommandError as e:
            can_run, err = False, e
        embed.add_field(name="Can use", value="Yes" if can_run else f"No: {err}")
        if flags := self.command_flags(command):
            embed.add_field(name="Flags", value="\n".join(flags))

        return embed

    async def send_command_help(
        self, command: commands.Command[Any, ..., Any], /
    ) -> None:
        await self.context.respond(embed=await self.command_embed(command))

    async def send_group_help(self, group: commands.Group[Any, ..., Any], /) -> None:

        subcommand_pages = commands.Paginator(prefix=None, suffix=None, max_size=1024)
        for cmd in await self.filter_commands(group.commands):
            subcommand_pages.add_line(f"- {self.command_display(cmd)}")

        base = await self.command_embed(group)
        embeds = [
            deepcopy(base).add_field(name="Subcommands", value=page)
            for page in subcommand_pages.pages
        ]
        await Pager([[embed] for embed in embeds], self.context.author).respond(
            self.context
        )

    async def send_cog_help(self, cog: commands.Cog, /) -> None:
        if not (commands := await self.filter_commands(cog.get_commands())):
            await self.context.respond(
                embed=self.base_embed(
                    title="No commands",
                    description="This cog doesn't have any commands.",
                )
            )
            return
        await self.context.respond(
            embed=self.base_embed(
                title=cog.__cog_name__, description=cog.description
            ).add_field(
                name="Commands",
                value="\n".join(f"- {self.command_display(cmd)}" for cmd in commands),
            )
        )

    async def send_bot_help(
        self,
        mapping: Mapping[commands.Cog | None, list[commands.Command[Any, ..., Any]]],
        /,
    ) -> None:
        split_embed = SplitEmbed.from_single(
            self.base_embed(
                title="Kolkra-NG help",
                description=self.context.bot.description,
            )
        )
        for cog, cmds in mapping.items():
            if not cmds:
                continue
            split_embed.add_field(
                name=cog.__cog_name__ if cog else "misc",
                value="\n".join(f"- {self.command_display(cmd)}" for cmd in cmds),
                inline=False,
            )
        await Pager(group_embeds(split_embed.embeds()), self.context.author).respond(
            self.context
        )

    async def send_error_message(self, error: str | None = None, /) -> None:
        if error:
            await self.context.respond(embed=self.base_embed(description=error))

    async def command_not_found(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, string: str, /
    ) -> str | None:
        all_commands = []
        for cmd in self.context.bot.commands:
            try:
                can_run: bool = await cmd.can_run(self.context)
            except commands.CommandError:
                can_run = False
            if can_run:
                all_commands.append(cmd.name)
                all_commands.extend(cmd.aliases)
        if (
            typo := get_close_matches(string, all_commands)
        ) and await Confirm().respond(
            self.context,
            embed=self.base_embed(
                description=f"{string!r} is not a known command or category. Did you mean: {typo[0]!r}?",
            ),
        ):
            await self.context.send_help(typo[0])
            return
        return (
            f"{string!r} is not a known command or category. "
            "Check your spelling, or type "
            f"`{self.context.clean_prefix}{self.context.invoked_with}`"
            " for a list of categories and commands."
        )

    def subcommand_not_found(
        self, command: commands.Command[Any, ..., Any], string: str, /
    ) -> str:
        return (
            f"{string!r} is not a subcommand of {command.qualified_name!r}. "
            f"Type `{self.context.clean_prefix}{self.context.invoked_with} {command.name}` "
            "for details on the parent command and a list of subcommands."
        )
