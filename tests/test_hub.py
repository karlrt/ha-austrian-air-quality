"""Unit tests for the shared fetch cycle.

``coordinator`` is the one module of this integration that really does need
Home Assistant, so there is no honest way to load it on a bare interpreter.
What these tests do instead is register a stand-in for the handful of Home
Assistant names it imports - the same trick ``test_api`` uses for ``aiohttp``,
one size up. The stand-in is deliberately thin: it does not reimplement Home
Assistant, it only lets the hub run so that its own logic can be exercised.

What it therefore does NOT cover: setup and unload of a config entry, the
entity platform, and everything else that only a real Home Assistant can tell
us. Those belong in the test instance.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

_PACKAGE = "austrian_air_quality_under_test"
_SOURCE = (
    Path(__file__).resolve().parents[1] / "custom_components" / "austrian_air_quality"
)


def _install_home_assistant_stub() -> None:
    """Register the Home Assistant names ``coordinator`` imports."""
    if "homeassistant" in sys.modules:  # pragma: no cover - real HA present
        return

    def _module(name: str, package: bool = False) -> types.ModuleType:
        module = types.ModuleType(name)
        if package:
            module.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = module
        return module

    _module("homeassistant", package=True)

    config_entries = _module("homeassistant.config_entries")

    class ConfigEntry:
        """Only the two attributes the hub reads off an entry."""

        def __init__(self, entry_id: str, options: dict | None = None) -> None:
            self.entry_id = entry_id
            self.options = options or {}

        def __class_getitem__(cls, _item: object) -> type:
            return cls

    config_entries.ConfigEntry = ConfigEntry  # type: ignore[attr-defined]

    core = _module("homeassistant.core")
    core.CALLBACK_TYPE = object  # type: ignore[attr-defined]
    core.callback = lambda func: func  # type: ignore[attr-defined]

    class HomeAssistant:
        """Enough of a Home Assistant to create tasks."""

        def __init__(self) -> None:
            self.data: dict = {}

        def async_create_task(
            self, target, name: str | None = None, eager_start: bool = True
        ):
            return asyncio.ensure_future(target)

    core.HomeAssistant = HomeAssistant  # type: ignore[attr-defined]

    exceptions = _module("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        """Home Assistant's reauth signal."""

    exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed  # type: ignore[attr-defined]

    _module("homeassistant.helpers", package=True)
    event = _module("homeassistant.helpers.event")

    def async_track_point_in_utc_time(hass, action, point):
        """Record the appointment and hand back a way to cancel it."""
        appointments = getattr(hass, "appointments", None)
        if appointments is None:
            appointments = hass.appointments = []
        appointment = [action, point, False]
        appointments.append(appointment)

        def unsub() -> None:
            appointment[2] = True

        return unsub

    event.async_track_point_in_utc_time = async_track_point_in_utc_time  # type: ignore[attr-defined]

    update_coordinator = _module("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        """Home Assistant's "this cycle did not work" exception."""

    class DataUpdateCoordinator:
        """The parts of the coordinator the integration builds on."""

        def __init__(
            self,
            hass,
            logger,
            *,
            config_entry=None,
            name: str | None = None,
            update_interval=None,
        ) -> None:
            self.hass = hass
            self.logger = logger
            self.config_entry = config_entry
            self.name = name
            self.update_interval = update_interval
            self.data = None
            self.last_update_success = True
            self.last_exception: Exception | None = None
            self.updates = 0

        def __class_getitem__(cls, _item: object) -> type:
            return cls

        def async_set_updated_data(self, data) -> None:
            self.data = data
            self.last_update_success = True
            self.updates += 1

        def async_set_update_error(self, err: Exception) -> None:
            self.last_update_success = False
            self.last_exception = err
            self.updates += 1

        async def async_refresh(self) -> None:
            try:
                self.data = await self._async_update_data()
            except Exception as err:  # noqa: BLE001 - mirrors the real behaviour
                self.last_update_success = False
                self.last_exception = err
            else:
                self.last_update_success = True
            self.updates += 1

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator  # type: ignore[attr-defined]
    update_coordinator.UpdateFailed = UpdateFailed  # type: ignore[attr-defined]

    _module("homeassistant.util", package=True)
    dt_module = _module("homeassistant.util.dt")
    dt_module.utcnow = lambda: datetime.now(timezone.utc)  # type: ignore[attr-defined]


_install_home_assistant_stub()

if _PACKAGE not in sys.modules:
    _stand_in = types.ModuleType(_PACKAGE)
    _stand_in.__path__ = [str(_SOURCE)]  # type: ignore[attr-defined]
    sys.modules[_PACKAGE] = _stand_in

try:  # pragma: no cover - depends on the interpreter the tests run on
    import aiohttp  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - the bare interpreter case
    _aiohttp = types.ModuleType("aiohttp")
    for _name in ("ClientSession", "ClientTimeout", "ClientError"):
        setattr(_aiohttp, _name, type(_name, (Exception,), {}))
    sys.modules["aiohttp"] = _aiohttp

api = importlib.import_module(f"{_PACKAGE}.api")
const = importlib.import_module(f"{_PACKAGE}.const")
coordinator_module = importlib.import_module(f"{_PACKAGE}.coordinator")
grouping = importlib.import_module(f"{_PACKAGE}.grouping")

ConfigEntry = sys.modules["homeassistant.config_entries"].ConfigEntry
HomeAssistant = sys.modules["homeassistant.core"].HomeAssistant
ConfigEntryAuthFailed = sys.modules["homeassistant.exceptions"].ConfigEntryAuthFailed

GRAZ_DON_BOSCO = (47.0675, 15.4133)
GRAZ_SUED = (47.0347, 15.4444)
GRAZ_SCHLOSSBERG = (47.0758, 15.4375)
WIEN = (48.2083, 16.3731)

# A selection with one pollutant, so the plans in these tests stay countable.
ONLY_PM10 = {
    const.OPT_MEASUREMENTS: ["pm10"],
    const.OPT_INDEXES: [],
    const.OPT_STATION_INDEX: False,
    const.OPT_LOCATION: False,
}
ONLY_NO2 = {
    const.OPT_MEASUREMENTS: ["no2"],
    const.OPT_INDEXES: [],
    const.OPT_STATION_INDEX: False,
    const.OPT_LOCATION: False,
}


class FakeApi:
    """Records every rectangle it is asked for."""

    def __init__(self, answers=None, failing: set[str] | None = None) -> None:
        self.calls: list[tuple[tuple[float, ...], tuple[str, ...], tuple]] = []
        self.answers = answers or {}
        self.failing = failing or set()

    async def async_fetch_group(self, bbox, station_ids, queries):
        self.calls.append((bbox, tuple(station_ids), tuple(queries)))
        if self.failing & set(station_ids):
            raise api.AustrianAirQualityConnectionError("no answer")
        return {
            station_id: self.answers.get(station_id, _station(station_id))
            for station_id in station_ids
            if station_id in self.answers or not self.answers
        }


def _station(station_id: str) -> api.AustrianAirQualityStation:
    return api.AustrianAirQualityStation(
        station_id=station_id,
        station_name=station_id,
        location=None,
        owner=None,
        latitude=None,
        longitude=None,
    )


def build(hass, hub, entry_id, station_id, position, options=ONLY_PM10):
    """A coordinator for one station, registered with the hub."""
    entry = ConfigEntry(entry_id, dict(options))
    made = coordinator_module.AustrianAirQualityCoordinator(
        hass, entry, hub, station_id, position[0], position[1]
    )
    hub.async_add(made)
    return made


class HubTestCase(unittest.IsolatedAsyncioTestCase):
    """Shared setup: a hub that does not sit around waiting."""

    def setUp(self) -> None:
        self._settle = coordinator_module.SETTLE_DELAY
        coordinator_module.SETTLE_DELAY = 0.0
        self.hass = HomeAssistant()

    def tearDown(self) -> None:
        coordinator_module.SETTLE_DELAY = self._settle

    def hub(self, fake_api: FakeApi) -> coordinator_module.AustrianAirQualityHub:
        return coordinator_module.AustrianAirQualityHub(self.hass, fake_api, phase=0)


class TestBundling(HubTestCase):
    """What the whole rebuild was for: requests stop following stations."""

    async def test_one_city_one_request_per_query(self) -> None:
        fake = FakeApi()
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        build(self.hass, hub, "b", "06:170", GRAZ_SUED)
        build(self.hass, hub, "c", "06:018", GRAZ_SCHLOSSBERG)

        await first.async_refresh()

        self.assertEqual(len(fake.calls), 1)
        _bbox, station_ids, queries = fake.calls[0]
        self.assertEqual(sorted(station_ids), ["06:018", "06:164", "06:170"])
        self.assertEqual(queries, (("pm10", const.MEANTYPE_CURRENT),))

    async def test_more_stations_do_not_cost_more_requests(self) -> None:
        for count in (1, 5):
            with self.subTest(stations=count):
                fake = FakeApi()
                hub = self.hub(fake)
                built = [
                    build(
                        self.hass,
                        hub,
                        f"entry{index}",
                        f"06:{index:03d}",
                        (GRAZ_DON_BOSCO[0] + index * 0.01, GRAZ_DON_BOSCO[1]),
                    )
                    for index in range(count)
                ]
                await built[0].async_refresh()
                self.assertEqual(len(fake.calls), 1)

    async def test_distant_stations_cost_one_request_each(self) -> None:
        fake = FakeApi()
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        build(self.hass, hub, "b", "09:STEF", WIEN)

        await first.async_refresh()

        self.assertEqual(len(fake.calls), 2)

    async def test_the_plan_is_the_union_of_the_selections(self) -> None:
        fake = FakeApi()
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO, ONLY_PM10)
        build(self.hass, hub, "b", "06:170", GRAZ_SUED, ONLY_NO2)

        await first.async_refresh()

        _bbox, _ids, queries = fake.calls[0]
        self.assertEqual(
            sorted(queries),
            [("no2", const.MEANTYPE_CURRENT), ("pm10", const.MEANTYPE_CURRENT)],
        )

    async def test_entries_starting_together_share_one_cycle(self) -> None:
        fake = FakeApi()
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        second = build(self.hass, hub, "b", "06:170", GRAZ_SUED)

        await asyncio.gather(first.async_refresh(), second.async_refresh())

        self.assertEqual(len(fake.calls), 1)
        self.assertIsNotNone(first.data)
        self.assertIsNotNone(second.data)


class TestDistribution(HubTestCase):
    """Every entry has to end up with its own station, and only its own."""

    async def test_each_entry_gets_its_own_station(self) -> None:
        fake = FakeApi()
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        second = build(self.hass, hub, "b", "06:170", GRAZ_SUED)

        await first.async_refresh()

        self.assertEqual(first.data.station_id, "06:164")
        self.assertEqual(second.data.station_id, "06:170")

    async def test_the_caller_is_not_served_twice(self) -> None:
        """It reads its station off the result; a push on top would double it."""
        fake = FakeApi()
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        build(self.hass, hub, "b", "06:170", GRAZ_SUED)

        await first.async_refresh()

        self.assertEqual(first.updates, 1)

    async def test_a_station_the_source_skips_is_not_a_failure(self) -> None:
        fake = FakeApi(answers={"06:164": _station("06:164")})
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        second = build(self.hass, hub, "b", "06:170", GRAZ_SUED)

        await first.async_refresh()

        self.assertIsNone(second.data)
        self.assertTrue(second.last_update_success)

    async def test_a_failed_rectangle_only_hits_its_own_stations(self) -> None:
        fake = FakeApi(failing={"09:STEF"})
        hub = self.hub(fake)
        near = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        far = build(self.hass, hub, "b", "09:STEF", WIEN)

        await near.async_refresh()

        self.assertIsNotNone(near.data)
        self.assertTrue(near.last_update_success)
        self.assertFalse(far.last_update_success)

    async def test_the_caller_sees_its_own_failure(self) -> None:
        fake = FakeApi(failing={"06:164"})
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)

        await first.async_refresh()

        self.assertFalse(first.last_update_success)

    async def test_an_auth_error_still_asks_for_reauth(self) -> None:
        class AuthFailingApi(FakeApi):
            async def async_fetch_group(self, bbox, station_ids, queries):
                raise api.AustrianAirQualityAuthError("HTTP 401")

        hub = self.hub(AuthFailingApi())
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)

        with self.assertRaises(ConfigEntryAuthFailed):
            await first._async_update_data()


class TestLifecycle(HubTestCase):
    """The timer comes with the first entry and goes with the last."""

    async def test_the_first_entry_starts_the_timer(self) -> None:
        hub = self.hub(FakeApi())
        build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        self.assertEqual(len(self.hass.appointments), 1)

    async def test_a_second_entry_does_not_start_a_second_timer(self) -> None:
        hub = self.hub(FakeApi())
        build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        build(self.hass, hub, "b", "06:170", GRAZ_SUED)
        self.assertEqual(len(self.hass.appointments), 1)

    async def test_the_last_entry_takes_the_timer_with_it(self) -> None:
        hub = self.hub(FakeApi())
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        second = build(self.hass, hub, "b", "06:170", GRAZ_SUED)

        self.assertFalse(hub.async_remove(first))
        self.assertFalse(self.hass.appointments[0][2])
        self.assertTrue(hub.async_remove(second))
        self.assertTrue(self.hass.appointments[0][2], "timer should be cancelled")

    async def test_a_removed_entry_is_no_longer_served(self) -> None:
        fake = FakeApi()
        hub = self.hub(fake)
        first = build(self.hass, hub, "a", "06:164", GRAZ_DON_BOSCO)
        second = build(self.hass, hub, "b", "06:170", GRAZ_SUED)
        hub.async_remove(second)

        await first.async_refresh()

        self.assertIsNone(second.data)
        _bbox, station_ids, _queries = fake.calls[0]
        self.assertEqual(station_ids, ("06:164",))


if __name__ == "__main__":
    unittest.main()
