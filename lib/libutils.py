import os
import numpy as np
from datetime import datetime, timedelta
from pytz import timezone
from lib.libdatabus import databus


def get_data_path(filename):
    dir_name = os.getenv("ROBOTFX_DATADIR")
    return os.path.join(dir_name, filename)


def count_business_days(date1, date2, holidays=[]):  # Does not count the first day and it counts the last.
    return int(np.busday_count(date1 + np.timedelta64(1, 'D'), date2 + np.timedelta64(1, 'D'), holidays=holidays))


def count_days(date1, date2):
    return int(np.int64((np.datetime64(date2) - np.datetime64(date1)) / np.timedelta64(1, "D")))


def get_maturity_adjusted(maturity, d_n, holidays=[]):
    return np.busday_offset(maturity, -(d_n - 1), holidays=holidays)


def get_today_str():
    return get_local_time().strftime("%Y-%m-%d")


def get_deltatime():
    delta_seconds = databus.get("TodayDelta")  # os.environ.get('DATETIME_DELTA')
    if delta_seconds:
        return timedelta(seconds=float(delta_seconds))

    return None


def get_local_time():
    # TODO: usar delta apenas se ambiente de des
    delta = get_deltatime()

    if delta is not None:
        return datetime.now() - delta

    return datetime.now()


def get_utc_time():
    # TODO: usar delta apenas se ambiente de des
    delta = get_deltatime()

    if delta is not None:
        return datetime.utcnow() - delta

    return datetime.utcnow()


def get_east_time():
    delta = get_deltatime()

    if delta is not None:
        return datetime.now(timezone("EST")) - delta

    return datetime.now(timezone("EST"))


def set_local_datetime(new_datetime):
    now = datetime.now()
    delta = now - new_datetime
    databus.set("TodayDelta", delta.total_seconds())
    # os.environ['DATETIME_DELTA'] = str(delta.total_seconds())


def get_local_timestamp():
    return get_local_time().timestamp()


def get_local_date():
    local_time = get_local_time()
    return local_time.date()


def get_validate_parameters():
    return ['YES', 'NO: GOOD-TODAY', 'NO: GOOD-TILL-CANCELLED']


def get_os_var(var_name):
    result = os.getenv(var_name)
    if result is None:
        log_info(f"{var_name} env var is not set")
    elif result == "":
        log_info(f"{var_name} string is empty")

    return result

def update_validate_rule(validate_rule, system_keyword, cnpj, is_ndf):
    rfq_type = "NDF" if is_ndf else "SPOT"
    if validate_rule.startswith('NO: GOOD-TODAY'):
        rule_date_str = validate_rule.split("|")[1]
        rule_date = np.datetime64(rule_date_str)
        today_str = get_today_str()
        today = np.datetime64(today_str)
        if rule_date != today:
            databus_key = f"TradingParameters/CounterpartyKeys/{cnpj}/FX{rfq_type}/Validate{system_keyword}"
            databus.set(databus_key, 'YES')
            return 'YES'
        else:
            return 'NO: GOOD-TODAY'
    else:
        return validate_rule



