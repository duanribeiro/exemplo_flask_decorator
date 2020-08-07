from bisect import bisect_left
from datetime import date
from datetime import timedelta
import numpy as np
import re
import traceback
from libdatabus import databus
from libutils import count_business_days
from libutils import count_days
from libutils import get_today_str
from liblog import print_red

previous_error_risk = None


def get_Lastdt(curve_name):
    return databus.get(f'MarketData/Curves/{curve_name}/LastUpdate')


def get_list_date_risk_curve(curve_name):
    bus_str = "MarketData/Curves/{curve_name}/dates".format(curve_name=curve_name)
    return databus.get(bus_str)


def get_list_rates_bid_risk_curve(curve_name):
    bus_str = "MarketData/Curves/{curve_name}/rates_bid".format(curve_name=curve_name)
    return databus.get(bus_str)


def get_list_rates_offer_risk_curve(curve_name):
    bus_str = "MarketData/Curves/{curve_name}/rates_offer".format(curve_name=curve_name)
    return databus.get(bus_str)


def get_risk_vertices_for_curve(curve_name):
    bus_str = "RiskData/CURVE/{curve_name}/RiskVertices".format(curve_name=curve_name)
    return databus.get(bus_str)


def get_str2date_list(a_list):
    return [date(*(int(e) for e in x.split("-"))) for x in a_list]


def is_business_day(date):
    # TODO: Handle holiday cases
    return date.weekday() not in (5, 6)


def get_next_date(date1, days):
    days_num = timedelta(days=days)
    return date1 + days_num


def get_next_business_date(date1, days):
    one_day = timedelta(days=1)
    current = date1
    counter = 0
    while counter < days:
        current += one_day
        if is_business_day(current):
            counter += 1
    return current


def calculate_interp_rate_expression(y_L, t_L, y_r, t_r, t, days=360.0):
    expression_L = (1.0 + y_L) ** (t_L / days)
    expression_R = (1.0 + y_r) ** (t_r / days)
    division = expression_R / expression_L
    core = division ** ((t - t_L) / (t_r - t_L))
    core *= expression_L
    return core ** (days / t) - 1


def get_reference_date():
    return np.datetime64(get_today_str())


def get_list_dates_risk_vertices(ref_date, risk_vertices_list, case_business_days=False):
    final_list = []
    cur_date = ref_date
    for num in risk_vertices_list:
        if case_business_days:
            final_list.append(get_next_business_date(cur_date, num))
        else:
            final_list.append(get_next_date(cur_date, num))
    return final_list


def convert_dates_to_days(ref_date, dates, use_business_days, holidays=None):
    if use_business_days:
        return map(lambda date_: count_business_days(ref_date, np.array(date_, dtype=np.datetime64), holidays), dates)
    else:
        return map(lambda date_: count_days(ref_date, date_), dates)


def get_lists_risk_curve(curve_name):
    config = databus.get_dict("Curves/{}".format(curve_name))
    print_red(f"DEBUG: get_lists_risk_curve(curve_name): config: {config}")
    curve_dates = get_list_date_risk_curve(curve_name)
    print_red(f"DEBUG: get_lists_risk_curve(curve_name): curves: {curve_dates}")
    if not curve_dates:
        raise Exception('Empty curves dates!')

    if config["DayCount"] == "BIZ":
        holidays = list(map(np.datetime64, databus.get("Calendars/{}".format(config.get("Currency"))),))
        curve_days = list(convert_dates_to_days(get_reference_date(), curve_dates, True, holidays))
    else:
        curve_days = list(convert_dates_to_days(get_reference_date(), curve_dates, False))

    curve_bid = get_list_rates_bid_risk_curve(curve_name)
    curve_offer = get_list_rates_offer_risk_curve(curve_name)
    risk_vertices = get_risk_vertices_for_curve(curve_name)

    interp_base = float(config.get("Base"))
    result_bid, result_offer = [], []

    for vertice in risk_vertices:
        idx_right = bisect_left(curve_days, vertice)
        if idx_right == 0:
            bid = curve_bid[0]
            offer = curve_offer[0]
        elif idx_right == len(curve_days):
            bid = curve_bid[-1]
            offer = curve_offer[-1]
        else:
            idx_left = idx_right - 1
            days_l = curve_days[idx_left]
            days_r = curve_days[idx_right]
            bid_l = curve_bid[idx_left]
            bid_r = curve_bid[idx_right]
            offer_l = curve_offer[idx_left]
            offer_r = curve_offer[idx_right]

            bid = calculate_interp_rate_expression(bid_l, days_l, bid_r, days_r, vertice, interp_base)
            offer = calculate_interp_rate_expression(offer_l, days_l, offer_r, days_r, vertice, interp_base)

        result_bid.append(bid)
        result_offer.append(offer)

    return result_bid, result_offer


def set_riskdata(curve_name, curve_dict):
    databus.update_from_dict(curve_dict, "RiskData/CURVE/{curve_name}".format(curve_name=curve_name))


def delete_riskdata(curve_names_tuple):
    for curve_name in curve_names_tuple:
        databus.delete(f"RiskData/CURVE/{curve_name}/RatesBid")
        databus.delete(f"RiskData/CURVE/{curve_name}/RatesOffer")
        databus.delete(f"RiskData/CURVE/{curve_name}/LastUpdate")


def treat_error(e, previous_error, curve_names_tuple):
    exp = re.compile(r"(<.*>)+")
    current_error = exp.sub("", repr(e))
    if previous_error != current_error:
        print(traceback.format_exc())
        delete_riskdata(curve_names_tuple)
        print("In Error", flush=True)

    return current_error


def update_riskdata():
    global previous_error_risk
    curve_names_tuple = tuple(databus.get('Curves'))
    print(f"DEBUG: update_riskdata: curve_names_tuple: {curve_names_tuple}")
    for curve_name in curve_names_tuple:
        try:
            print(f"DEBUG: update_riskdata: curve_name: {curve_name}")
            bid_list, offer_list = get_lists_risk_curve(curve_name)
            curve_dict = {"RatesBid": bid_list, "RatesOffer": offer_list, "LastUpdate": get_Lastdt(curve_name)}
            set_riskdata(curve_name, curve_dict)
            if previous_error_risk is not None:
                print("Recovered", flush=True)
                previous_error_risk = None
        except Exception as e:
            previous_error_risk = treat_error(e, previous_error_risk, curve_names_tuple)
            # curves_timestamp = {curve_name: None for curve_name in curve_names_tuple}
