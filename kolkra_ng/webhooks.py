from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Protocol, runtime_checkable

from discord import Client, HTTPException, NotFound, Thread, Webhook, WebhookMessage
from discord.utils import MISSING


@runtime_checkable
class SupportsWebhooks(Protocol):
    async def webhooks(self) -> list[Webhook]: ...
    async def create_webhook(
        self,
        *,
        name: str,
        avatar: bytes | None = None,
        reason: str | None = None,
    ) -> Webhook: ...


class WebhookManager:
    """A simple class that juggles webhooks for different channels."""

    _hooks: dict[SupportsWebhooks, list[Webhook]]

    def __init__(self, client: Client) -> None:
        self.client = client
        self._hooks = {}

    async def init_hooks(self, channel: SupportsWebhooks) -> list[Webhook]:
        """Sets up webhooks for a channel.

        Args:
            channel (SupportsWebhooks): The channel to set up the hooks for.

        Returns:
            list[Webhook]: The webhooks set up for this channel.
        """
        if not isinstance(channel, SupportsWebhooks):
            raise TypeError()
        usable_hooks = [
            hook for hook in await channel.webhooks() if hook.user == self.client.user
        ]
        while len(usable_hooks) < 2:
            usable_hooks.append(
                await channel.create_webhook(
                    name="Kolkra-NG",
                )
            )
        self._hooks[channel] = usable_hooks
        return usable_hooks

    async def send(
        self, destination: SupportsWebhooks | Thread, *args, **kwargs
    ) -> WebhookMessage | None:
        """Sends a message through a managed webhook for a channel or thread.

        Args:
            channel (SupportsWebhooks | Thread): The channel to send the message in.

        Raises:
            HTTPException: Discord returned a status other than 429. (in which case the manager will recursively try again with another webhook)
            ValueError: The webhook source was not found.

        Returns:
            WebhookMessage | None: The sent webhook if wait=True, else None.
        """
        is_thread = isinstance(destination, Thread)
        if not (hook_source := (destination.parent if is_thread else destination)):
            raise ValueError()
        if not (hooks := self._hooks.get(hook_source)) or len(hooks) < 2:
            hooks = await self.init_hooks(hook_source)
        hook = hooks.pop(0)
        try:
            msg = await hook.send(
                *args,
                **kwargs,
                thread=destination if is_thread else MISSING,
            )
        except NotFound:
            return await self.send(
                destination, *args, **kwargs
            )  # The webhook doesn't exist anymore--why put it back once we're done with it?
        except HTTPException as e:
            if e.status == 429:
                msg = await self.send(destination, *args, **kwargs)
            else:
                raise
        hooks.append(hook)
        return msg

    @asynccontextmanager
    async def acquire_hook(
        self, channel: SupportsWebhooks
    ) -> AsyncGenerator[Webhook, None]:
        """Manually acquire a webhook for a channel.
        For 99.9% of use cases, you should just use `.send`.
        You should only use this if you know what you are doing and are willing/able to handle potential errors yourself.

        Args:
            channel (SupportsWebhooks): The channel to acquire a webhook for.

        Yields:
            Webhook: A webhook for the channel.
        """
        hook = self._hooks[channel].pop(0)
        try:
            yield hook
        finally:
            self._hooks[channel].append(hook)
