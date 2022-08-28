"""
Financial functions and calculations
"""


async def calculate_event_price(session_participants, session_hours, workshop_participants,
                                workshop_hours) -> dict:
    """
    Calculate event cost for event creator
    """
    # meaning of class = interval of participant max number e.g. 1 to 5 participant is class A and
    # static number of class A is 10 and discount is 1%
    # Base number * hours * static number for class * static discount for class

    # mock calculations
    session_cost = session_participants * session_hours
    workshop_cost = workshop_participants * workshop_hours

    data = {'workshop_cost': workshop_cost, 'session_cost': session_cost}

    return data
