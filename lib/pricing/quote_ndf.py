# -*- coding: utf-8 -*-
import os
import numpy as np
import datetime as dt
import libep
import messages
from validation.validate import PotentialFutureExposure
from libutils import count_business_days
from libutils import count_days
from libutils import get_today_str
from libutils import get_maturity_adjusted
from libexceptions import RejectException
from libexceptions import ResultHasntChanged
from libexceptions import raise_if_none
from libdatabus import databus
from libdatabus_utils import get_holidays

log_error = libep.log_error
log_info = libep.log_info


# TODO: qual a regra de extrapolacao; mover para utils.
def interpolation(xs, ys, x, base):
    if x <= xs[0]:
        return ys[0]
    elif x >= xs[-1]:
        return ys[-1]

    idx_r = np.searchsorted(xs, x)
    xl, xr = xs[idx_r - 1], xs[idx_r]
    yl, yr = ys[idx_r - 1], ys[idx_r]

    base = float(base)
    yyr = (1 + yr) ** (xr / base)
    yyl = (1 + yl) ** (xl / base)
    m = (x - xl) / float(xr - xl)
    y = (yyl * ((yyr / yyl) ** m)) ** (base / x) - 1

    return y


def get_or_raise(key, message):
    value = databus.get(key)
    if value is None:
        raise RejectException(message)

    return value


class PriceNDFBase:
    class Result:
        def __init__(self):
            self.spread = None
            self.fop = None
            self.fmin = None
            self.quote = None
            self.revenue_brl = None
            self.present_value_brl = None
            self.present_value_ccy = None
            self.brl_risk = None
            self.spread_risk = None
            self.spread_notional = None
            self.dc = None
            self.du = None
            self.dn = None
            self.pre_brl = None
            self.cupom_ccy = None
            self.s_cost = None
            self.f_cost = None
            self.s_client = None
            self.forward_points = None
            self.value_brl = None
            self.y_brl = None
            self.y_ccy = None
            self.y_ccy_client = None
            self.f_pfe = None
            self.side = None
            self.validate_kyc = None
            self.validate_isda = None
            self.adjusted_maturity = None
            self.precision = None

        def has_changed(self, quote, precision, revenue_brl):
            has_quote_changed = f'{quote:.{precision}f}' != f'{self.quote:.{precision}f}'
            has_revenue_changed = revenue_brl / self.revenue_brl - 1 > 0.01
            return has_quote_changed or has_revenue_changed

    def __init__(self):
        self.result = None

    def price(self):
        self.check_autoflow_limits()

        brl = self.get_brl()
        ccy = self.get_ccy()
        today = self.get_today()
        fixing = self.get_fixing()
        maturity = self.get_maturity()
        amount = self.get_amount()
        holidays_brl = get_holidays(brl)
        d_n = count_business_days(fixing, maturity, holidays_brl)
        maturity_adjusted = get_maturity_adjusted(maturity, d_n, holidays=holidays_brl)
        dc = count_days(today, maturity_adjusted)
        du = count_business_days(today, maturity_adjusted, holidays=holidays_brl)

        self.check_max_days_to_maturity(dc)

        ccy_discount_curve_name = self.get_discount_curve_name(ccy)
        brl_discount_curve_name = self.get_discount_curve_name(brl)

        ccy_curve_dates = self.get_discount_curve_dates(ccy_discount_curve_name)
        brl_curve_dates = self.get_discount_curve_dates(brl_discount_curve_name)

        side = self.get_side()

        if side == 'Buy':
            ys_brl = self.get_discount_curve_values(brl_discount_curve_name, 'bid')
            ys_ccy = self.get_discount_curve_values(ccy_discount_curve_name, 'offer')
        else:
            ys_brl = self.get_discount_curve_values(brl_discount_curve_name, 'offer')
            ys_ccy = self.get_discount_curve_values(ccy_discount_curve_name, 'bid')

        dus_brl = list(map(lambda x: count_business_days(today, x, holidays=holidays_brl), brl_curve_dates))
        dcs_ccy = list(map(lambda x: count_days(today, x), ccy_curve_dates))

        y_brl = round(interpolation(dus_brl, ys_brl, du, 252), 6)
        y_ccy = interpolation(dcs_ccy, ys_ccy, dc, 360)
        y_ccy = round(((1 + y_ccy) ** (dc / 360.0) - 1) * (360.0 / dc), 6)

        precision = self.get_currency_precision(ccy)

        s_cost = self.get_scost(ccy, 'Ask' if side != 'Buy' else 'Bid')
        s_cost = round(s_cost, precision)

        f_cost = s_cost * ((1 + y_brl) ** (du / 252.0)) / (1 + y_ccy * (dc / 360.0))
        f_cost = round(f_cost, precision)

        lower_limit_revenue = self.get_lower_limit_revenue(ccy)
        fmin = (lower_limit_revenue / amount) * ((1 + y_brl) ** (du / 252))

        spread = self.get_spread(self.get_cnpj(), ccy, dc)
        fop = max(fmin, spread)  # TODO: add ceiling
        signal = -1 if side == 'Sell' else 1
        quote = f_cost - (fop * signal)
        y_ccy_custo = ((s_cost / quote) * (1 + y_brl) ** (du / 252.0) - 1) * (360.0 / dc)
        quote = round(quote, precision)

        if quote <= 0.0:
            raise RejectException('Notional abaixo do parâmetro e-sales (receita)')

        if side == 'Buy':
            s_client = y_ccy_custo - y_ccy
            revenue = amount * abs(quote - f_cost) / ((1 + y_brl) ** (du / 252.0))
        else:
            s_client = y_ccy - y_ccy_custo
            revenue = amount * abs(f_cost - quote) / ((1 + y_brl) ** (du / 252.0))

        y_ccy_custo = round(y_ccy_custo, 6)
        s_client = round(s_client, 6)

        if self.result:
            if not self.result.has_changed(quote, precision, revenue):
                raise ResultHasntChanged()

        # cálculo do valor presente, se robo esta vendendo, valor deve ser negativo;
        present_value_brl = round(s_cost * (amount / (1 + y_ccy * (dc / 360.0))) * signal, 2)
        present_value_ccy = round(present_value_brl / s_cost, precision)

        # TODO: apagar esse trecho de código. O propósito desse trecho abaixo é para conseguir realizar
        # alguns testes no BV.
        if os.getenv('DATA_CONSULTA_PFE'):
            data_consulta_dt = dt.datetime.strptime(os.getenv('DATA_CONSULTA_PFE'), '%Y-%m-%d')
            log_info(f'data da consulta pdf = {data_consulta_dt}')
        else:
            data_consulta_dt = self.get_today().astype(dt.datetime)

        pfe_inst = PotentialFutureExposure()

        try:
            pfe_success = pfe_inst.execute(
                ccy=self.get_ccy(), side=self.get_side(), prazo_consumo=dc, data_consulta=data_consulta_dt
            )
        except Exception:
            raise  # TODO: tratar erro de maneira adequada

        f_pfe = pfe_success.value  # prep_and_get_pfe(self, dc)
        brl_risk = f_pfe * abs(present_value_brl) + revenue

        spread_risk = (1 + revenue / brl_risk) ** (360.0 / dc) - 1
        spread_notional = (1 + revenue / abs(present_value_brl)) ** (360.0 / dc) - 1

        self.result = PriceNDFBase.Result()
        self.result.spread = fop
        self.result.pre_brl = y_brl
        self.result.cupom_ccy = y_ccy
        self.result.fop = fop
        self.result.fmin = fmin
        self.result.quote = quote
        self.result.value_brl = round(quote * amount, 2)
        self.result.revenue_brl = revenue
        self.result.present_value_brl = present_value_brl
        self.result.present_value_ccy = present_value_ccy
        self.result.brl_risk = brl_risk
        self.result.spread_risk = spread_risk
        self.result.spread_notional = spread_notional
        self.result.dc = dc
        self.result.du = du
        self.result.dn = d_n  # business days entre fixing e settlement.
        self.result.s_cost = s_cost
        self.result.f_cost = f_cost
        self.result.s_client = s_client
        self.result.forward_points = round(quote - s_cost, precision)
        self.result.y_brl = y_brl
        self.result.y_ccy = y_ccy
        self.result.y_ccy_client = y_ccy_custo
        self.result.f_pfe = f_pfe
        self.result.side = side
        self.result.adjusted_maturity = str(maturity_adjusted)
        self.result.precision = precision
        return self.result


class PriceNDFBRL(PriceNDFBase):
    '''especializacao da implementacao do pricer para FX Spot'''

    def __init__(self, quote_request):
        super().__init__()
        self.brl = 'BRL'
        self.ccy = quote_request.Currency
        self.symbol = quote_request.Symbol
        # self.fut_sett_date = quote_request.FutSettDate
        # self.fut_sett_date2 = quote_request.FutSettDate2
        self.side = 'Buy' if quote_request.Side == messages.EnumSide.SELL else 'Sell'  # se cliente compra, robo vende
        self.cnpj = quote_request.CustomerID
        self.amount = quote_request.OrderQty
        self.fixing = np.datetime64(quote_request.FixingDate)
        self.maturity = np.datetime64(quote_request.FutSettDate)

        raise_if_none(self.ccy, 'Falta moeda da transação')
        raise_if_none(self.symbol, 'Falta paridade da transação')
        raise_if_none(self.side, 'Falta a posição buy ou sell')
        raise_if_none(self.cnpj, 'CNPJ de cadastro cliente Bloomberg inválido')

    def check_max_days_to_maturity(self, days):
        ccy = self.get_ccy()
        key = f'TradingParameters/CurrencyKeys/{ccy}/FXNDF/UpperLimitDays2Maturity'
        limit = get_or_raise(key, f'Erro ao consultar limite máximo para vencimento ({ccy})')

        if days > limit:
            msg = 'Vencimento acima do parâmetro e-sales (moeda)'
            raise RejectException(msg)

        key = f'TradingParameters/CounterpartyKeys/{self.cnpj}/FXNDF/UpperLimitDays2Maturity'
        limit = get_or_raise(key, 'Erro ao consultar limite máximo para vencimento (contraparte)')

        if days > limit:
            msg = 'Vencimento acima do parâmetro e-sales (contraparte)'
            raise RejectException(msg)

    def check_autoflow_limits(self):
        ccy = self.get_ccy()

        key_max = f'TradingParameters/CurrencyKeys/{ccy}/FXNDF/MaximumAmountAutoFlow'
        max_autoflow = get_or_raise(key_max, 'Erro ao consultar limite superior para notional')

        if max_autoflow is not None and self.amount > max_autoflow:
            msg = 'Notional acima do parâmetro e-sales'
            raise RejectException(msg)

        key_min = f'TradingParameters/CurrencyKeys/{ccy}/FXNDF/MinimumAmountAutoFlow'
        min_autoflow = get_or_raise(key_min, 'Erro ao consultar limite inferior para notional')
        if min_autoflow is not None and self.amount < min_autoflow:
            msg = 'Notional abaixo do parâmetro e-sales'
            raise RejectException(msg)

        key_max = f'FXSupplierControl/{ccy}/MaxQuantity'
        max_autoflow_supplier = get_or_raise(key_max, 'Erro ao consultar limite superior para notinal (fx supplier)')

        if max_autoflow_supplier is not None and self.amount > max_autoflow_supplier:
            msg = 'Notional acima do parâmetro fx-supplier'
            raise RejectException(msg)

    def get_today(self):
        str_today = get_today_str()  # databus.get('Today/Date')
        raise_if_none(str_today, 'Erro ao consultar data corrente')
        try:
            today = np.datetime64(str_today)
        except ValueError:
            raise Exception('Data corrente inválida')

        return today

    def get_amount(self):
        return self.amount

    def get_bid_or_ask(self):
        return 'Bid' if self.side == 'Buy' else 'Ask'

    def get_brl(self):
        return self.brl

    def get_ccy(self):
        return self.ccy

    def get_cnpj(self):
        return self.cnpj

    def get_discount_curve_name(self, ccy):
        return get_or_raise(f'Currencies/{ccy}/DiscountCurve', "Erro ao consultar a curva de desconto")

    def get_discount_curve_dates(self, curve):
        dates = get_or_raise(f'MarketData/Curves/{curve}/dates', 'Erro ao consultar a curva de desconto (datas)')
        return list(map(np.datetime64, dates))

    def get_discount_curve_values(self, curve, bid_offer):
        return get_or_raise(
            f'MarketData/Curves/{curve}/rates_{bid_offer}', 'Erro ao consultar curva de desconto (valores)'
        )

    def get_currency_precision(self, ccy):
        return get_or_raise(f'Currencies/{ccy}/Precision', 'Número de casas decimais inválido')

    def get_lower_limit_revenue(self, ccy):
        return get_or_raise(
            f'TradingParameters/CurrencyKeys/{ccy}/FXNDF/LowerLimitRevenue',
            f'Erro ao consultar limite inferior de receita para moeda {ccy}',
        )

    def get_scost(self, ccy, bid_or_ask):
        return get_or_raise(f'FXSupplierData/NDF/{ccy}BRL/{bid_or_ask}', 'Erro de consulta da taxa spot')

    def get_side(self):
        return self.side

    def get_fixing(self):
        return self.fixing

    def get_maturity(self):
        return self.maturity

    def get_spread(self, cnpj, ccy, dc):
        def get_bucket(buckets):
            bucket = None
            for index in range(0, len(buckets)):
                if int(buckets[index]) >= dc:
                    bucket = index
                    break

            return bucket

        buckets = databus.get(f'ClientSpreads/CounterpartySpreads/{cnpj}/FXNDF/Buckets')
        spreads = databus.get(f'ClientSpreads/CounterpartySpreads/{cnpj}/FXNDF/Spreads/{ccy}/BUYSELL')
        bucket = get_bucket(buckets) if buckets is not None else None
        counterparty_valid_spread = True

        if None in (bucket, spreads) or (spreads and spreads[bucket] is None):
            counterparty_valid_spread = False

        if not counterparty_valid_spread:
            group_name = databus.get(f'LegalEntitiesRelationships/Groups_Spreads_FXNDF_Memberships/{cnpj}')
            if group_name is None or group_name == "":
                raise RejectException(f'Spread não cadastrado para CNPJ/Grupo')

            buckets = databus.get(f'ClientSpreads/GroupSpreads/{group_name}/FXNDF/Buckets')
            spreads = databus.get(f'ClientSpreads/GroupSpreads/{group_name}/FXNDF/Spreads/{ccy}/BUYSELL')

            bucket = get_bucket(buckets) if buckets is not None else None
            if None in (bucket, spreads) or (spreads and spreads[bucket] is None):
                raise RejectException('Spread não cadastrado para CNPJ/Grupo')

        return spreads[bucket]

    def get_symbol(self):
        return self.symbol
