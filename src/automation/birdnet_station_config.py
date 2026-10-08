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

    latitude = os.getenv(f"BIRDNET_{station}_LATITUDE", "").strip()
    longitude = os.getenv(f"BIRDNET_{station}_LONGITUDE", "").strip()
    if bool(latitude) != bool(longitude):
        raise ValueError("Configure both station latitude and longitude, or neither.")
    config["latitude"] = float(latitude) if latitude else None
    config["longitude"] = float(longitude) if longitude else None
    if latitude and not (-90 <= config["latitude"] <= 90 and -180 <= config["longitude"] <= 180):
        raise ValueError("Station coordinates are outside valid ranges.")
    return config