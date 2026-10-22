"""Validated finite retention limits; pending/uncertain work never expires."""

DEFAULTS = {
    "outbox": {"max_events": 1000, "max_bytes": 8388608,
               "acked_retention_seconds": 604800, "receipt_retention_seconds": 2592000, "receipt_limit": 4000},
    "inbox": {"max_events": 1000, "max_bytes": 8388608,
              "max_completed": 1000, "completed_retention_seconds": 2592000},
    "dispatcher": {"max_events": 128, "max_bytes": 262144,
                   "max_completed": 128, "completed_retention_seconds": 2592000},
}


def limits(section, supplied=None):
    if section not in DEFAULTS or supplied is not None and not isinstance(supplied, dict):
        raise ValueError("invalid_storage_policy")
    supplied = supplied or {}
    if set(supplied) - set(DEFAULTS[section]):
        raise ValueError("unknown_storage_policy_field")
    value = {**DEFAULTS[section], **supplied}
    for key, item in value.items():
        minimum = 65536 if key == "max_bytes" else 0 if key.endswith("seconds") else 1
        maximum = 31536000 if key.endswith("seconds") else DEFAULTS[section][key]
        if type(item) is not int or not minimum <= item <= maximum:
            raise ValueError("storage_policy_out_of_bounds")
    return value
