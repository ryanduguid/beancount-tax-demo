"""Reject ambiguous JSON objects and non-standard numeric constants."""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON property")
        result[key] = value
    return result


def reject_json_constant(value):
    raise ValueError("non-standard JSON numeric constant")
