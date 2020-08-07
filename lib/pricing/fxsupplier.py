# -*- coding: utf-8 -*-
import datetime
import numpy as np
from calendar import monthrange
from libdatabus import databus
from libdatabus_utils import get_holidays
from libutils import get_local_date
from libep import log_info


class MarketValueException(Exception):
    pass


def get_last_business_day(year, month):
    """ Returns last business day in a given month
    """
    holidays_brl = get_holidays('BRL')
    last_date = np.datetime64(datetime.date(year, month, monthrange(year, month)[1]))

    while last_date.astype(object).day > 1:
        if np.is_busday(last_date, holidays=holidays_brl):
            return last_date.astype(object).day

        last_date = last_date - np.timedelta64(1, 'D')

    raise Exception('Invalid last business day')


def update_databus(s_cost, usd_future_bid, usd_future_ask):
    databus.update_from_dict(s_cost, 'FXSupplierData')
    databus.set('MarketData/Futures/USDBRL/Active/Bid', usd_future_bid)
    databus.set('MarketData/Futures/USDBRL/Active/Ask', usd_future_ask)


class SupplierEngine(object):
    def __init__(self):
        self.usdbrl_origin = 'UC1'
        today = get_local_date()

        # in case today is the last business day in a given month
        if get_last_business_day(today.year, today.month) == today.day:
            self.usdbrl_origin = 'UC2'

        log_info(f'supplier using {self.usdbrl_origin}')
        self.currencies = {}
        self.currencies_precision = {}
        self.currencies_type = {}

    def load_currencies(self):
        self.currencies = databus.get('Currencies')

        if not self.currencies:
            self.currencies = {}
            self.currencies_precision = {}
            self.currencies_type = {}
            return

        self.currencies_precision = {}
        self.currencies_type = {}

        for ccy in self.currencies:
            # TODO: caso não seja encontrada a precisão para uma moeda, cancelar a moeda!
            self.currencies_precision[ccy] = databus.get(f'Currencies/{ccy}/Precision')
            self.currencies_type[ccy] = databus.get(f'Currencies/{ccy}/Type')

    def update_s_cost(self):
        if not self.currencies or not self.currencies_precision or not self.currencies_type:
            self.load_currencies()

        usd_precision = self.currencies_precision['USD']
        usd_future_bid = databus.get(f'MarketData/Futures/USDBRL/{self.usdbrl_origin}/Bid')
        usd_future_ask = databus.get(f'MarketData/Futures/USDBRL/{self.usdbrl_origin}/Ask')

        if usd_future_bid is not None and usd_future_ask is not None:
            usd_future_bid = round(usd_future_bid, usd_precision)
            usd_future_ask = round(usd_future_ask, usd_precision)

        s_cost = {'SPOT': {}, 'NDF': {}}

        if not usd_future_bid or not usd_future_ask:
            for code in self.currencies:
                if code.upper() == 'BRL':
                    continue
                codebrl = '{}BRL'.format(code)
                s_cost['SPOT'][codebrl] = {'Bid': None, 'Ask': None}
                s_cost['NDF'][codebrl] = {'Bid': None, 'Ask': None}

            update_databus(s_cost, None, None)  # Erase s_const if can't find future data

            raise MarketValueException("Can't find market value for UC1/UC2 Future")

        casado = databus.get('FXSupplierCasado/Price')
        usdbrl_bid = round(usd_future_bid - casado, usd_precision)
        usdbrl_ask = round(usd_future_ask - casado, usd_precision)

        for code in self.currencies:
            if code.upper() == 'BRL':
                continue

            ccy_precision = self.currencies_precision[code]

            if code.upper() != 'USD':
                ccy_type = self.currencies_type[code]

                if ccy_type.upper() not in ['A', 'B']:
                    raise Exception('can\'t find currency {code} type'.format(code=code))

                ccy_pair = ('USD{code}' if ccy_type.upper() == 'A' else '{code}USD').format(code=code)
                ccy_bid = databus.get('MarketData/CurrencyPairs/{pair}/Bid'.format(pair=ccy_pair))
                ccy_ask = databus.get('MarketData/CurrencyPairs/{pair}/Ask'.format(pair=ccy_pair))

                if not ccy_bid or not ccy_ask:
                    continue

                if ccy_type.upper() == 'A':
                    ccybrl_bid = usdbrl_bid / ccy_bid
                    ccybrl_ask = usdbrl_ask / ccy_ask
                elif ccy_type == 'B':
                    ccybrl_bid = usdbrl_bid * ccy_bid
                    ccybrl_ask = usdbrl_ask * ccy_ask
            else:
                ccybrl_bid = usdbrl_bid
                ccybrl_ask = usdbrl_ask

            markup_buy = databus.get('FXSupplierControl/{code}/MarkupBUY'.format(code=code))
            markup_sell = databus.get('FXSupplierControl/{code}/MarkupSELL'.format(code=code))

            if not markup_buy or not markup_sell:
                raise Exception('can\'t find fx supplier markup for {code}'.format(code=code))

            ccybrl_bid = round(ccybrl_bid, ccy_precision)
            ccybrl_ask = round(ccybrl_ask, ccy_precision)

            s_cost_bid = round(ccybrl_bid - markup_buy, self.currencies_precision[code])
            s_cost_ask = round(ccybrl_ask + markup_sell, self.currencies_precision[code])

            codebrl = '{}BRL'.format(code)
            s_cost['SPOT'][codebrl] = {'Bid': s_cost_bid, 'Ask': s_cost_ask}
            s_cost['NDF'][codebrl] = {'Bid': ccybrl_bid, 'Ask': ccybrl_ask}

        # colocar s_cost no barramento e Futures Active.
        update_databus(s_cost, usd_future_bid, usd_future_ask)
