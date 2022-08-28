"""Users core functions"""


def serve_partial_update_user_nested_info(incoming_info_dict: dict) -> dict:
    """Serving user's nested information"""

    returning_info_dict = {}
    for field, value in incoming_info_dict.items():
        if type(value) is dict:
            for (nested_field, nested_value) in value.items():
                returning_info_dict.update({f'{field}.{nested_field}': nested_value})
        else:
            returning_info_dict.update({f'{field}': value})
    return returning_info_dict
