"""Eligibility based on the property register and retained station history."""
import json

def species_key(name):
    return " ".join(str(name or "").split()).casefold()

def build_history(detections, config):
    first = {}
    for row in detections:
        key = species_key(row.get("scientificName"))
        if not key:
            raise ValueError("History contains a detection without a scientific name.")
        detection_id = int(row["id"])
        first[key] = min(first.get(key, detection_id), detection_id)
    return {"station": config["station"], "property": config["property"],
            "source_base_url": config["base_url"], "first_retained_ids": first}

def review_eligibility(register, detection, config, history_path):
    if register.get("status") != "completed":
        raise ValueError("Species-list check has not completed.")
    membership = register.get("already_in_register")
    if membership is False:
        return {"eligible": True, "reason": "absent_from_property_species_list"}
    if membership is not True:
        raise ValueError("Species-list membership is unknown.")
    if not history_path.exists():
        return {"eligible": False, "reason": "station_history_unavailable",
                "requires_review": True}
    history = json.loads(history_path.read_text(encoding="utf-8"))
    for field in ("station", "property", "source_base_url"):
        expected = config["base_url"] if field == "source_base_url" else config[field]
        if history.get(field) != expected:
            raise ValueError("Station history provenance mismatch.")
    key = species_key(detection.get("scientificName"))
    first = history["first_retained_ids"].get(key)
    if first is None:
        return {"eligible": False, "reason": "species_missing_from_history_snapshot",
                "requires_review": True}
    eligible = int(detection["id"]) == int(first)
    return {"eligible": eligible, "reason": "first_retained_station_detection" if eligible
            else "known_species_at_station", "first_retained_detection_id": first}
