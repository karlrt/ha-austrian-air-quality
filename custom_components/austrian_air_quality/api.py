"""Client für die Luftqualitätsdaten des Umweltbundesamts.

ACHTUNG – PLATZHALTER.

Die konkrete Schnittstelle ist noch nicht verifiziert. Bevor hier implementiert
wird, muss geklärt sein:

* Basis-URL und Endpunkte (Stationsliste, Messwerte)
* Antwortformat (JSON / CSV / XML) und Feldnamen je Schadstoff
* Einheiten je Schadstoff und Mittelungszeitraum (HMW, MW1, TMW ...)
* Aktualisierungsintervall der Quelle und ein dazu passendes Polling-Intervall
* Nutzungsbedingungen / Lizenz der Daten und ob ein API-Key nötig ist

Bis dahin liefern die Methoden bewusst NotImplementedError, damit kein
Scheinbetrieb entsteht.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from aiohttp import ClientSession

# TODO: verifizierte Basis-URL eintragen.
API_BASE_URL = "https://TODO.invalid/"

REQUEST_TIMEOUT = 30


class AustrianAirQualityApiError(Exception):
    """Allgemeiner Fehler beim Zugriff auf die Datenquelle."""


class AustrianAirQualityAuthError(AustrianAirQualityApiError):
    """Authentifizierung fehlgeschlagen bzw. Zugriff verweigert."""


class AustrianAirQualityConnectionError(AustrianAirQualityApiError):
    """Die Datenquelle war nicht erreichbar."""


@dataclass(slots=True)
class AustrianAirQualityStation:
    """Eine Messstation."""

    station_id: str
    name: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(slots=True)
class AustrianAirQualityMeasurements:
    """Messwerte einer Station zu einem Zeitpunkt.

    ``values`` bildet Schadstoffschlüssel (siehe const.POLLUTANTS) auf den
    Messwert ab. Fehlende Schadstoffe fehlen im Dict.
    """

    station: AustrianAirQualityStation
    measured_at: datetime | None = None
    values: dict[str, float] = field(default_factory=dict)


class AustrianAirQualityApi:
    """Asynchroner Client für die Luftqualitätsdaten."""

    def __init__(self, session: ClientSession, base_url: str = API_BASE_URL) -> None:
        """Client initialisieren."""
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def async_get_stations(self) -> list[AustrianAirQualityStation]:
        """Liste der verfügbaren Messstationen abrufen."""
        raise NotImplementedError(
            "Stationsabruf noch nicht implementiert – Datenquelle ist ungeklärt."
        )

    async def async_get_measurements(self, station_id: str) -> AustrianAirQualityMeasurements:
        """Aktuelle Messwerte einer Station abrufen."""
        raise NotImplementedError(
            "Messwertabruf noch nicht implementiert – Datenquelle ist ungeklärt."
        )
