"""Reads vehicle status from Kia UVO portal."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import LENGTH_KILOMETERS

from . import DOMAIN as KIA_DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "doors": ["Doors", "door"],
    "door_lock_state": ["Door lock state", "lock"]
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Kia sensors."""
    accounts = hass.data[KIA_DOMAIN]
    _LOGGER.debug("Found Kia accounts: %s", ", ".join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        for vehicle in account.account.vehicles:
            _LOGGER.debug("Kia Vehicle")
            for key, value in sorted(SENSOR_TYPES.items()):
                device = KiaUvoSensor(
                    account, vehicle, key, value[0], value[1]
                )
                devices.append(device)
    add_entities(devices, True)


class KiaUvoSensor(BinarySensorDevice):
    """Representation of a BMW vehicle binary sensor."""

    def __init__(self, account, vehicle, attribute: str, sensor_name, device_class):
        """Constructor."""
        self._account = account
        self._vehicle = vehicle
        self._attribute = attribute
        self._name = "{} {}".format(self._vehicle.vehicle["nickName"], self._attribute)
        self._unique_id = "{}-{}".format(self._vehicle.vehicle["vehicleId"], self._attribute)
        self._sensor_name = sensor_name
        self._device_class = device_class
        self._state = None

    @property
    def should_poll(self) -> bool:
        """Return False.
        Data update is triggered from BMWConnectedDriveEntity.
        """
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        vehicle_state = self._vehicle
        result = {"car": vehicle_state.vehicle["nickName"]}

        if self._attribute == "doors":
            result["Hood"] = vehicle_state.status["hoodOpen"]
            result["Trunk"] = vehicle_state.status["trunkOpen"]
            result["FrontLeft"] = vehicle_state.status["doorOpen"]["frontLeft"] == 1
            result["FrontRight"] = vehicle_state.status["doorOpen"]["frontRight"] == 1
            result["BackLeft"] = vehicle_state.status["doorOpen"]["backLeft"] == 1
            result["BackRight"] = vehicle_state.status["doorOpen"]["backRight"] == 1

        return sorted(result.items())

    def update(self):
        """Read new state data from the library."""

        vehicle_state = self._vehicle

        # device class opening: On means open, Off means closed
        if self._attribute == "doors":
            doors_open = vehicle_state.status["hoodOpen"] \
                         or vehicle_state.status["trunkOpen"] \
                         or vehicle_state.status["doorOpen"]["frontLeft"] == 1 \
                         or vehicle_state.status["doorOpen"]["frontRight"] == 1 \
                         or vehicle_state.status["doorOpen"]["backLeft"] == 1 \
                         or vehicle_state.status["doorOpen"]["backRight"] == 1
            _LOGGER.debug("Status of lid: %s", doors_open)
            self._state = doors_open

        elif self._attribute == "door_lock_state":
            self._state = not vehicle_state.status["doorLock"]

    def update_callback(self):
        """Schedule a state update."""
        self._vehicle = [i for i, _ in enumerate(self._account.account.vehicles) if
                         _.vehicle['vehicleId'] == self._vehicle.vehicle["vehicleId"]][0]

        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.
        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
