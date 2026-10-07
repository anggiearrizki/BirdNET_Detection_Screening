"""BirdNET-Go station configuration.

Each BirdNET-Go station has its own detection ID sequence and therefore
maintains separate scanner state and review queues.

Multiple stations may belong to the same property.
"""

import os

from dotenv import load_dotenv


load_dotenv()


STATIONS = {
    "CEMPEDAK_MAIN_KAMONG": {
        "property": "Cempedak",
        "station": "CEMPEDAK_MAIN_KAMONG",
        "display_name": "Main / Kamong",
        "base_url": os.getenv(
            "BIRDNET_CEMPEDAK_MAIN_KAMONG_BASE_URL",
            "",
        ).rstrip("/"),
    },

    "CEMPEDAK_SOUTH_SIDE": {
        "property": "Cempedak",
        "station": "CEMPEDAK_SOUTH_SIDE",
        "display_name": "South side",
        "base_url": os.getenv(
            "BIRDNET_CEMPEDAK_SOUTH_SIDE_BASE_URL",
            "",
        ).rstrip("/"),
    },
}


def get_station_config(
    station,
):
    """Return configuration for a BirdNET-Go station."""

    station = station.strip().upper()

    if station not in STATIONS:
        raise ValueError(
            f"Unknown BirdNET station: {station}"
        )

    config = STATIONS[
        station
    ].copy()

    if not config[
        "base_url"
    ]:
        raise RuntimeError(
            f"No base URL configured for {station}."
        )

    return config