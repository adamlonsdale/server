"""
Home Assistant Plugin for Music Assistant.

The plugin is the core of all communication to/from Home Assistant and
responsible for maintaining the WebSocket API connection to HA.
Also, the Music Assistant integration within HA will relay its own api
communication over the HA api for more flexibility as well as security.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import shortuuid
from hass_client import HomeAssistantClient
from hass_client.utils import (
    async_is_supervisor,
    base_url,
    get_auth_url,
    get_long_lived_token,
    get_token,
    get_websocket_url,
)

from music_assistant.common.models.config_entries import ConfigEntry, ConfigValueType
from music_assistant.common.models.enums import ConfigEntryType
from music_assistant.common.models.errors import LoginFailed
from music_assistant.constants import MASS_LOGO_ONLINE
from music_assistant.server.helpers.auth import AuthenticationHelper
from music_assistant.server.models.plugin import PluginProvider

if TYPE_CHECKING:
    from music_assistant.common.models.config_entries import ProviderConfig
    from music_assistant.common.models.provider import ProviderManifest
    from music_assistant.server import MusicAssistant
    from music_assistant.server.models import ProviderInstanceType

DOMAIN = "hass"
CONF_URL = "url"
CONF_AUTH_TOKEN = "token"
CONF_ACTION_AUTH = "auth"


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize provider(instance) with given configuration."""
    prov = HomeAssistant(mass, manifest, config)
    await prov.handle_setup()
    return prov


async def get_config_entries(
    mass: MusicAssistant,
    instance_id: str | None = None,  # noqa: ARG001
    action: str | None = None,
    values: dict[str, ConfigValueType] | None = None,
) -> tuple[ConfigEntry, ...]:
    """
    Return Config entries to setup this provider.

    instance_id: id of an existing provider instance (None if new instance setup).
    action: [optional] action key called from config entries UI.
    values: the (intermediate) raw values for config entries sent with the action.
    """
    # config flow auth action/step (authenticate button clicked)
    if action == CONF_ACTION_AUTH:
        hass_url = values[CONF_URL]
        async with AuthenticationHelper(mass, values["session_id"]) as auth_helper:
            client_id = base_url(auth_helper.callback_url)
            auth_url = get_auth_url(
                hass_url,
                auth_helper.callback_url,
                client_id=client_id,
                state=values["session_id"],
            )
            result = await auth_helper.authenticate(auth_url)
        if result["state"] != values["session_id"]:
            msg = "session id mismatch"
            raise LoginFailed(msg)
        # get access token after auth was a success
        token_details = await get_token(hass_url, result["code"], client_id=client_id)
        # register for a long lived token
        long_lived_token = await get_long_lived_token(
            hass_url,
            token_details["access_token"],
            client_name=f"Music Assistant {shortuuid.random(6)}",
            client_icon=MASS_LOGO_ONLINE,
            lifespan=365 * 2,
        )
        # set the retrieved token on the values object to pass along
        values[CONF_AUTH_TOKEN] = long_lived_token

    if await async_is_supervisor():
        # on supervisor, we use the internal url
        # token set to None for auto retrieval
        return (
            ConfigEntry(
                key=CONF_URL,
                type=ConfigEntryType.STRING,
                label=CONF_URL,
                required=True,
                default_value="http://supervisor/core/api",
                value="http://supervisor/core/api",
            ),
            ConfigEntry(
                key=CONF_AUTH_TOKEN,
                type=ConfigEntryType.STRING,
                label=CONF_AUTH_TOKEN,
                required=False,
                default_value=None,
                value=None,
            ),
        )
    # manual configuration
    return (
        ConfigEntry(
            key=CONF_URL,
            type=ConfigEntryType.STRING,
            label="URL",
            required=True,
            description="URL to your Home Assistant instance (e.g. http://192.168.1.1:8123)",
            value=values.get(CONF_URL) if values else None,
        ),
        ConfigEntry(
            key=CONF_ACTION_AUTH,
            type=ConfigEntryType.ACTION,
            label="(re)Authenticate Home Assistant",
            description="Authenticate to your home assistant "
            "instance and generate the long lived token.",
            action=CONF_ACTION_AUTH,
            depends_on=CONF_URL,
            required=False,
        ),
        ConfigEntry(
            key=CONF_AUTH_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label="Authentication token for HomeAssistant",
            description="You can either paste a Long Lived Token here manually or use the "
            "'authenticate' button to generate a token for you with logging in.",
            depends_on=CONF_URL,
            value=values.get(CONF_AUTH_TOKEN) if values else None,
            advanced=True,
        ),
    )


class HomeAssistant(PluginProvider):
    """Home Assistant Plugin for Music Assistant."""

    hass: HomeAssistantClient

    async def handle_setup(self) -> None:
        """Handle async initialization of the plugin."""
        url = get_websocket_url(self.config.get_value(CONF_URL))
        token = self.config.get_value(CONF_AUTH_TOKEN)
        self.hass = HomeAssistantClient(url, token, self.mass.http_session)
        await self.hass.connect()

    async def unload(self) -> None:
        """
        Handle unload/close of the provider.

        Called when provider is deregistered (e.g. MA exiting or config reloading).
        """
        await self.hass.disconnect()
