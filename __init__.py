"""Reads vehicle status from Kia UVO portal."""
import datetime
import logging

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import discovery
from homeassistant.helpers.event import track_utc_time_change
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "kia_uvo"
CONF_READ_ONLY = "read_only"
ATTR_VIN = "vin"

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_READ_ONLY, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: {cv.string: ACCOUNT_SCHEMA}}, extra=vol.ALLOW_EXTRA)

SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_VIN): cv.string})


KIA_COMPONENTS = ["binary_sensor", "device_tracker", "lock", "sensor"]
UPDATE_INTERVAL = 5  # in minutes

SERVICE_UPDATE_STATE = "update_state"

_SERVICE_MAP = {
}


def setup(hass, config: dict):
    """Set up the Kia Uvo components."""
    accounts = []
    for name, account_config in config[DOMAIN].items():
        accounts.append(setup_account(account_config, hass, name))

    hass.data[DOMAIN] = accounts

    def _update_all(call) -> None:
        """Update all Kia accounts."""
        for cd_account in hass.data[DOMAIN]:
            cd_account.update()

    # Service to manually trigger updates for all accounts.
    hass.services.register(DOMAIN, SERVICE_UPDATE_STATE, _update_all)

    _update_all(None)

    for component in KIA_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


def setup_account(account_config: dict, hass, name: str) -> "KiaUvoAccount":
    """Set up a new KiaUvoAccount based on the config."""
    username = account_config[CONF_USERNAME]
    password = account_config[CONF_PASSWORD]
    read_only = account_config[CONF_READ_ONLY]

    _LOGGER.debug("Adding new account %s", name)
    cd_account = KiaUvoAccount(username, password, name, read_only)

    # update every UPDATE_INTERVAL minutes, starting now
    # this should even out the load on the servers
    now = datetime.datetime.now()
    track_utc_time_change(
        hass,
        cd_account.update,
        minute=range(now.minute % UPDATE_INTERVAL, 60, UPDATE_INTERVAL),
        second=now.second,
    )

    return cd_account


class KiaUvoAccount:
    """Representation of a Kia vehicle."""

    def __init__(
        self, username: str, password: str, name: str, read_only
    ) -> None:
        """Constructor."""
        from KiaUvo import KiaUvo

        self.read_only = read_only
        self.name = name
        self.account = KiaUvo(username, password)

        self._update_listeners = []

    def update(self, *_):
        """Update the state of all vehicles.
        Notify all listeners about the update.
        """
        _LOGGER.debug(
            "Updating vehicle state for account %s, notifying %d listeners",
            self.name,
            len(self._update_listeners),
        )
        try:
            self.account.login()
            vehicles = self.account.get_vehicle_list()
            for listener in self._update_listeners:
                listener(vehicles)
        except IOError as exception:
            _LOGGER.error("Error updating the vehicle state")
            _LOGGER.exception(exception)

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)
