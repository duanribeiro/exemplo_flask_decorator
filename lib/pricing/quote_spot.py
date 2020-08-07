import numpy as np
import messages
from libutils import get_local_time
from libutils import get_today_str
from libexceptions import RejectException
from libexceptions import ResultHasntChanged
from libexceptions import raise_if_none
from libdatabus import databus


def get_or_raise(key, message):
    value = databus.get(key)
    if value is None:
        raise RejectException(message)

    return value


class PriceSpotBase:
    class Result:
        def __init__(self):
            self.quote = None
            self.spread = None
            self.amount_brl = None
            self.revenue_brl = None
            self.ccy_dus = None
            self.settlement_ccy = None
            self.settlement_brl = None
            self.amount_usd = None
            self.revenue_brl = None
            self.settlement_date_ccy = None
            self.settlement_date_brl = None
            self.usd_parity = None
            self.s_cost = None
            self.precision = None
            self.validate_kyc = None  # preenchido pelo endpoint

        def has_changed(self, quote, precision):
            has_quote_changed = f'{quote:.{precision}f}' != f'{self.quote:.{precision}f}'
            return has_quote_changed

    def __init__(self):
        self.result = None

    def price(self):
        '''implementação do modelo de precificação de um instrumento SPOT'''
        brl = self.get_brl()
        ccy = self.get_ccy()

        today = self.get_today()
        sett_date_ccy = self.get_settlement_date(self.ccy)
        du_brl = self.du_brl
        du_ccy = self.du_ccy

        self.check_autoflow_limits(du_ccy)
        self.check_cutoff(du_ccy)

        dc = np.int64((sett_date_ccy - today) / np.timedelta64(1, 'D'))

        r_brl = self.get_settlement_rate(brl)
        r_ccy = self.get_settlement_rate(ccy)

        usd_future = self.get_usdbrl_future(self.get_bid_or_ask())
        casado = self.get_casado()
        usdbrl_quote = usd_future - casado

        s_cost = self.get_scost(ccy, self.get_bid_or_ask())
        s_cost_ccybrl = s_cost * ((1 + r_ccy) ** ((2 - dc) / 360.0)) / ((1 + r_brl) ** ((2 - du_brl) / 252.0))
        precision = self.get_currency_precision(ccy)
        s_cost_ccybrl = round(s_cost_ccybrl, precision)

        cnpj = self.get_cnpj()
        spread = self.get_spread(cnpj, ccy, self.get_side(), du_ccy)

        if self.get_side() == 'Buy':
            s_client = s_cost_ccybrl - float(spread)
        else:
            s_client = s_cost_ccybrl + float(spread)

        if s_client <= 0.0:
            raise RejectException('Notional abaixo do Parâmetro e-sales')

        if self.result:
            if not self.result.has_changed(s_client, precision):
                raise ResultHasntChanged()

        s_client = round(s_client, precision)
        self.result = PriceSpotBase.Result()
        self.result.quote = s_client
        self.result.spread = float(spread)
        self.result.settlement_ccy = du_ccy
        self.result.settlement_brl = du_brl
        self.result.amount_brl = round(self.get_amount() * s_client, 2)
        self.result.amount_usd = round(self.get_amount() * usdbrl_quote)
        self.result.revenue_brl = round(self.get_amount() * float(spread), 2)
        self.result.settlement_date_ccy = str(sett_date_ccy)
        self.result.settlement_date_brl = str(self.get_settlement_date(self.brl))
        self.result.usdbrl_quote = usdbrl_quote
        self.result.s_cost = s_cost
        self.result.precision = precision
        return self.result


class PriceSpotBRL(PriceSpotBase):
    '''especialização da implementação do pricer para FX Spot'''

    def __init__(self, quote_request):
        super().__init__()
        self.brl = 'BRL'
        self.ccy = quote_request.Currency
        self.symbol = quote_request.Symbol
        self.fut_sett_date = np.datetime64(quote_request.FutSettDate)
        self.side = 'Buy' if quote_request.Side == messages.EnumSide.SELL else 'Sell'  # se cliente compra, robo vende
        self.cnpj = quote_request.CustomerID
        self.amount = quote_request.OrderQty

        # SettlQualifier = 0, significa split settlement
        if quote_request.SettlQualifier == '0':
            self.fut_sett_date2 = np.datetime64(quote_request.FutSettDate2)
        else:
            self.fut_sett_date2 = self.fut_sett_date

        raise_if_none(self.ccy, 'Falta moeda da transação')
        raise_if_none(self.symbol, 'Falta paridade da moeda')
        raise_if_none(self.fut_sett_date, f'Data settlement inválida ({self.ccy})')
        raise_if_none(self.fut_sett_date2, 'Data settlement inválida (brl)')
        raise_if_none(self.side, 'Falta a posição buy ou sell')
        raise_if_none(self.cnpj, 'CNPJ de cadastro cliente Bloomberg inválido')

        self.du_brl, self.du_ccy = self.check_dates_and_get_day_count()

    def check_cutoff(self, settlement):
        market_type = get_or_raise(f"LegalEntities/{self.cnpj}/FXMarketType", "Erro ao consultar tipo de mercado")

        key = 'SpotConfig/CutOffTimes/'
        if market_type and str(market_type) == '2':  # cliente interbancário
            cutoff = get_or_raise(f"{key}Secundary/Any/d{settlement}", "Erro ao consultar cutoff")
        else:
            ccy = self.get_ccy()
            cutoff = get_or_raise(f"{key}Primary/{ccy}/d{settlement}", f"Erro ao consultar cutoff (ccy)")

        if cutoff == '-':
            raise RejectException('Transação acima do horário de corte')

        hh_cutoff, mm_cutoff = map(int, cutoff.split(':'))
        now = get_local_time().time()  # dt.datetime.now().time()

        if now.hour > hh_cutoff or (now.hour == hh_cutoff and now.minute > mm_cutoff):
            raise RejectException('Transação acima do horário de corte')

    def check_dates_and_get_day_count(self):
        sett_date_brl = self.get_settlement_date(self.get_brl())
        sett_date_ccy = self.get_settlement_date(self.get_ccy())
        sett_grid_ccy = self.get_settlement_grid(self.get_ccy())

        if sett_date_brl not in sett_grid_ccy:
            dates_str = ' '.join(map(str, sett_grid_ccy))
            raise RejectException(f'Data de settlement inválida (datas válidas: {dates_str})')

        if sett_date_ccy not in sett_grid_ccy:
            dates_str = ' '.join(map(str, sett_grid_ccy))
            raise RejectException(f'Data de settlement inválida (datas válidas: {dates_str})')

        du_brl = sett_grid_ccy.index(sett_date_brl)
        du_ccy = sett_grid_ccy.index(sett_date_ccy)

        market_type = get_or_raise(f"LegalEntities/{self.cnpj}/FXMarketType", "Erro ao consultar tipo de mercado")

        if market_type is None:
            raise RejectException(f'Erro ao consultar tipo de mercado')
        elif str(market_type) == '2':  # cliente interbancário
            if du_brl != du_ccy:
                raise RejectException(f'Settlement descasado para operação no mercado secundário')

        return du_brl, du_ccy

    def check_autoflow_limits(self, dus_settlement):
        ccy = self.get_ccy()

        key_max = f'TradingParameters/CurrencyKeys/{ccy}/FXSPOT/MaximumAmountAutoFlow'
        if dus_settlement in (0, 1):
            key_max += '_d{}'.format(str(dus_settlement))

        max_autoflow = get_or_raise(key_max, 'Erro ao consultar limite superior para notional')
        if max_autoflow is not None and self.amount > max_autoflow:
            msg = f'Notional acima do parâmetro e-sales'
            raise RejectException(msg)

        key_min = f'TradingParameters/CurrencyKeys/{ccy}/FXSPOT/MinimumAmountAutoFlow'
        min_autoflow = get_or_raise(key_min, 'Erro ao consultar limite inferior para notional')
        if min_autoflow is not None and self.amount < min_autoflow:
            msg = f'Notional abaixo do parâmetro e-sales'
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
        return float(self.amount)

    def get_bid_or_ask(self):
        return 'Bid' if self.side == 'Buy' else 'Ask'

    def get_brl(self):
        return self.brl

    def get_ccy(self):
        return self.ccy

    def get_cnpj(self):
        return self.cnpj

    def get_usdbrl_future(self, bid_or_ask):
        return get_or_raise(f'MarketData/Futures/USDBRL/Active/{bid_or_ask}', 'Erro ao consultar futuros')

    def get_casado(self):
        return get_or_raise('FXSupplierCasado/Price', 'Erro ao consultar casado')

    def get_currency_precision(self, ccy):
        return get_or_raise(f'Currencies/{ccy}/Precision', 'Número de casas decimais inválido')

    def get_scost(self, ccy, bid_or_ask):
        s_cost = get_or_raise(f'FXSupplierData/SPOT/{ccy}BRL/{bid_or_ask}', 'Erro ao consultar a taxa spot')
        return float(s_cost)

    def get_side(self):
        return self.side

    def get_settlement_rate(self, ccy):
        value = get_or_raise(f'FXSupplierControl/{ccy}/SettlementRate', 'Tesouraria: falta taxa juros (pré/cupom)')
        return float(value)

    def get_settlement_date(self, ccy):
        if ccy == self.brl:
            return self.fut_sett_date2

        return self.fut_sett_date

    def get_settlement_grid(self, ccy):
        sett_grid_ccy = get_or_raise(f'Today/SettlementGrid/{ccy}', f'Grid de settlement inválido ({ccy})')

        try:
            sett_grid_ccy = list(map(np.datetime64, sett_grid_ccy))
        except ValueError:
            raise Exception('Data de settlement inválida')

        return sett_grid_ccy

    def get_spread(self, cnpj, ccy, side, du_ccy):
        side = side.upper()  # side foi colocado em upper no barramento.
        spreads = databus.get(f'ClientSpreads/CounterpartySpreads/{cnpj}/FXSPOT/{ccy}/{side}')

        if spreads is None or spreads[du_ccy] is None:
            group_name = databus.get(f'LegalEntitiesRelationships/Groups_Spreads_FXSPOT_Memberships/{cnpj}')
            if group_name is None or group_name == "":
                raise RejectException('Spread não cadastrado para CNPJ/Grupo')

            spreads = databus.get(f'ClientSpreads/GroupSpreads/{group_name}/FXSPOT/{ccy}/{side}')
            raise_if_none(spreads, 'Spread não cadastrado para CNPJ/Grupo')

            spread = spreads[du_ccy]
            raise_if_none(spread, 'Spread não cadastrado para CNPJ/Grupo')
        else:
            spread = spreads[du_ccy]

        return spread

    def get_symbol(self):
        return self.symbol

    def get_init_du_brl(self):
        return self.du_brl

    def get_init_du_ccy(self):
        return self.du_ccy
