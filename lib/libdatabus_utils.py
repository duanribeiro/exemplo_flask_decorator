import numpy as np
from libdatabus import databus


def get_holidays(currency):
    holidays = databus.get('Calendars/{ccy}'.format(ccy=currency))
    if holidays is not None:
        return list(map(np.datetime64, holidays))

    return []
