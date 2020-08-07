import bisect
import json
import redis
import lib.messages as messages
from lib.libdatabus import databus
from lib.libutils import get_local_timestamp

r = redis.StrictRedis()


def get_quoterequest_msg(quoterequest_id):
    return get_transaction(messages.QuoteRequest.getMsgType(), quoterequest_id)


def set_transaction(msg, details=None):
    msg_code = msg.get_message_code()
    current_status = get_transaction_status(msg.QuoteReqID)

    if msg_code not in messages.Flow[current_status]:
        if msg_code == messages.Code.Quote:  # ignora cotação que chegar atrasada
            return

        raise RuntimeError(f'ID: {msg.QuoteReqID}: {msg_code} is not a valid sequence to {current_status}')

    msg_id = msg.get_message_id()
    msg_str = messages.serialize_to_json(msg)
    pack = json.dumps({'msg': msg_str})
    entry = {msg.MsgType: {msg_id: pack}}
    databus.update_from_dict(entry, 'Transactions/Messages')
    databus.update_from_dict({msg.QuoteReqID: msg_code}, 'Transactions/Status')
    if msg_code == messages.Code.Quote:
        databus.update_from_dict({msg.QuoteReqID: msg.QuoteID}, 'Transactions/LastQuoteID')
    set_timestamp(msg.QuoteReqID, msg_code, get_local_timestamp())
    update_blotter(msg)

    r.publish('history', json.dumps({"info": "transaction", "publish_data": msg_str}))


def set_timestamp(msg_id, msg_code, value):
    if msg_code != 'Quote':
        result = databus.get(f'Transactions/Metrics/{msg_id}')
        if result is not None:
            j = json.loads(result)
        else:
            j = {'timestamps': {}}
        j['timestamps'][msg_code] = value
        pack = json.dumps(j)
        databus.update_from_dict({msg_id: pack}, 'Transactions/Metrics')
    else:  # for Quote is a list of timestamps
        result = databus.get(f'Transactions/Metrics/{msg_id}')
        j = json.loads(result)
        if 'Quote' not in j['timestamps'].keys():
            j['timestamps'][msg_code] = []
        j['timestamps'][msg_code].append(get_local_timestamp())
        pack = json.dumps(j)
        databus.update_from_dict({msg_id: pack}, 'Transactions/Metrics')

    r.publish('history', json.dumps({"info": "metrics", "publish_data": {'pack': pack, 'msg_id': msg_id}}))


class StatsTracker:
    def __init__(self, msg_id, msg_code):
        self.msg_id = msg_id
        self.msg_code = msg_code
        self.ts_gavg = 0
        self.count = 0
        self.ts_min = 9999
        self.ts_max = 0
        self.ts_avg = 0

    def update(self, ts_d):
        self.count += 1
        if ts_d < self.ts_min:
            self.ts_min = ts_d
        if ts_d > self.ts_max:
            self.ts_max = ts_d
        self.ts_avg = self.ts_avg * (self.count - 1) / self.count + ts_d / self.count
        set_timestamp(self.msg_id, "max-" + self.msg_code, self.ts_max)
        set_timestamp(self.msg_id, "min-" + self.msg_code, self.ts_min)
        set_timestamp(self.msg_id, "avg-" + self.msg_code, self.ts_avg)


def get_transaction(msg_type, msg_id):
    result = databus.get(f'Transactions/Messages/{msg_type}/{msg_id}')
    if result:
        j = json.loads(result)
        msg = messages.parse_from_json(j.get('msg'))
        return msg, j.get('details')

    return None, None


def get_transaction_status(quoterequest_id):
    return databus.get(f'Transactions/Status/{quoterequest_id}')


def update_balance_ndf(ccy, amount_ccy, amount_pv, amount_brl, revenue_brl, side, dc):
    def incr_by(key, value):
        db_key = f'Balance/NDF/{ccy}/{key}'
        databus.increase_by_float(db_key, value)

    incr_by('TotalAmount', amount_ccy)
    incr_by('NetPV', amount_pv)
    incr_by('NetPV_BRL', amount_brl)
    incr_by('NetAmount', amount_ccy if side.lower() == 'buy' else -amount_ccy)
    incr_by('Revenue_BRL', revenue_brl)
    incr_by(f'{side}/TotalPV', amount_pv)
    incr_by(f'{side}/TotalAmount', abs(amount_ccy))

    partial_pv_key = f'Balance/NDF/{ccy}/{side}/PartialPV'
    partial_pv_list = databus.get(partial_pv_key)
    tuple_partial_pvs_max_dcs = (1, 31, 61, 91, 181, 361, 721)
    idx = bisect.bisect_right(tuple_partial_pvs_max_dcs, dc) - 1
    partial_pv_list[idx] += amount_pv
    databus.set(partial_pv_key, partial_pv_list)

    partial_amount_key = f'Balance/NDF/{ccy}/{side}/PartialAmount'
    partial_amount_list = databus.get(partial_amount_key)
    idx = bisect.bisect_right(tuple_partial_pvs_max_dcs, dc) - 1
    partial_amount_list[idx] += abs(amount_ccy)
    databus.set(partial_amount_key, partial_amount_list)


def update_balance_spot(ccy, amount, side, days_count, revenue_brl):
    def incr_by(key, value):
        db_key = f'Balance/SPOT/{ccy}/{key}/{side}D{days_count}'
        databus.increase_by_float(db_key, value)

    incr_by('TotalAmount', amount)
    incr_by('TotalRevenue', revenue_brl)


def increase_cash_limits_spot(ccy, amount, n):
    db_key = f'CashLimits/SPOT/{ccy}/d{n}'
    if databus.get(db_key) is None:
        return False, f"Limite de caixa não definido para {ccy} D+{n}"

    databus.increase_by_float(db_key, amount)
    databus.publish('cash-limits-spot', 1)
    return True, ''


def decrease_cash_limits_spot(ccy, amount, n, reset=False):
    db_key = f'CashLimits/SPOT/{ccy}/d{n}'
    if databus.get(db_key) is None:
        return False, f"Limite de caixa não definido para {ccy} D+{n}"

    try:
        if not databus.decrease_if_greater_than(db_key, amount, reset):
            return False, f"Fundos insuficientes para {ccy} D+{n}"
    except RuntimeError:
        return False, "Operação inválida"

    databus.publish('cash-limits-spot', 1)
    return True, ''


def get_fix_field(field, msg):
    if msg.isSetField(field):
        return msg.getField(field)

    return '-'


def round_if_valid(value, precision):
    if value is not None:
        if isinstance(value, float) and isinstance(precision, int):
            return round(value, precision)

    return value


def blotter_generic_quote_request(quoterequest):
    if quoterequest.SecurityType == messages.EnumSecurityType.SPOT:
        security_type = 'FXSPOT'
    elif quoterequest.SecurityType == messages.EnumSecurityType.NDF:
        security_type = 'FXNDF'

    model = {
        'quote_req_id': quoterequest.QuoteReqID,
        'color': 'orange',
        'mtype': 'RFQ',
        'cnpj': None,
        'counterparty': quoterequest.CustomerStr,
        'client_side': quoterequest.Side,
        'security_type': security_type,
        'dealcode': quoterequest.CustomerDealCode,
        'amount': quoterequest.OrderQty,
        'symbol': quoterequest.Symbol,
        'currency': quoterequest.Currency,
        'notes': quoterequest.Text,
    }

    model['cnpj'] = quoterequest.CustomerID
    model['counterparty'] = databus.get(f'LegalEntities/{quoterequest.CustomerID}/CounterpartyName')
    return model


def blotter_generic_neworder(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    model['mtype'] = 'NEW.ORDER'
    return model


def blotter_generic_deal(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    if msg.Type == messages.ExecReportType.ACCEPT:
        model['mtype'] = 'EXECUTING'
    else:
        model['mtype'] = 'EXP.QUOTE'
    return model


def blotter_generic_reject_response(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    model['mtype'] = 'REJECTED'
    model['color'] = 'red'
    model['rejected_text'] = msg.Text
    return model


def blotter_generic_reject_request(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    model['mtype'] = 'NOTH.DONE'
    model['rejected_text'] = msg.Text
    return model


def blotter_generic_quote(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    model['mtype'] = 'QUOTE'
    model['buy'] = '-' if msg.BidPx is None else msg.BidPx
    model['sell'] = '-' if msg.OfferPx is None else msg.OfferPx
    return model


def blotter_generic_quote_cancel(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    model['mtype'] = 'TIMEOUT'
    return model


def blotter_generic_exec_ack_unknown(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    model['mtype'] = 'ACK.UNKNOWN'
    return model


def blotter_generic_exec_ack(msg):
    strmodel = databus.get(f'Blotter/{msg.QuoteReqID}')
    model = json.loads(strmodel)
    model['color'] = '#49ed6d'
    model['mtype'] = 'DEAL'
    return model


def update_blotter_spot(msg):
    model = None

    if isinstance(msg, messages.QuoteRequest):
        model = blotter_generic_quote_request(msg)
        model['settlement_ccy'] = msg.FutSettDate
        model['settlement_brl'] = msg.FutSettDate2
        du_ccy = msg.Ccy1SettlementDU if msg.Ccy1SettlementDU is not None else '?'
        du_brl = msg.Ccy2SettlementDU if msg.Ccy2SettlementDU is not None else '?'
        model['settlement_ccy_dn'] = f"d+{du_ccy}"
        model['settlement_brl_dn'] = f"d+{du_brl}"
        model['timestamp'] = msg.TransactTime

    elif isinstance(msg, messages.ExecReport):
        model = blotter_generic_deal(msg)

    elif isinstance(msg, messages.NewOrderSingle):
        # The blotter is updated with the information of the Quote message whose ID
        # is referenced in the NewOrder message (msg.QuoteID)
        quote, _ = get_transaction(messages.Quote.getMsgType(), msg.QuoteID)
        model = blotter_generic_neworder(msg)
        model['buy'] = '-' if quote.BidPx is None else quote.BidPx
        model['sell'] = '-' if quote.OfferPx is None else quote.OfferPx
        if quote.Details:
            precision = quote.Details.get('precision')
            model['spread'] = quote.Details.get('spread')
            model['revenue'] = quote.Details.get('revenue_brl')
            model['s_cost'] = round_if_valid(quote.Details.get('s_cost'), precision)
            model['validate_kyc'] = quote.Details.get('validate_kyc')

    elif isinstance(msg, messages.QuoteReject):
        if msg.Origin == messages.RejectOrigin.PRICER:
            model = blotter_generic_reject_response(msg)
        else:
            model = blotter_generic_reject_request(msg)

    elif isinstance(msg, messages.QuoteCancel):
        model = blotter_generic_quote_cancel(msg)

    elif isinstance(msg, messages.ExecAcknowledgmentUnknown):
        model = blotter_generic_exec_ack_unknown(msg)

    elif isinstance(msg, messages.ExecAcknowledgment):
        model = blotter_generic_exec_ack(msg)

    elif isinstance(msg, messages.Quote):
        model = blotter_generic_quote(msg)
        precision = msg.Details.get('precision')
        model['spread'] = msg.Details.get('spread')
        model['revenue'] = msg.Details.get('revenue_brl')
        model['s_cost'] = round_if_valid(msg.Details.get('s_cost'), precision)
        model['validate_kyc'] = msg.Details.get('validate_kyc')

    return model


def update_blotter_ndf(msg):
    model = None

    if isinstance(msg, messages.QuoteRequest):
        model = blotter_generic_quote_request(msg)
        if msg.FutSettDate:
            model['maturity'] = msg.FutSettDate  # .item().strftime('%Y-%m-%d')
        model['timestamp'] = msg.TransactTime

    elif isinstance(msg, messages.ExecReport):
        model = blotter_generic_deal(msg)

    elif isinstance(msg, messages.NewOrderSingle):
        # The blotter is updated with the information of the Quote message whose ID
        # is referenced in the NewOrder message (msg.QuoteID)
        quote, _ = get_transaction(messages.Quote.getMsgType(), msg.QuoteID)
        model = blotter_generic_neworder(msg)
        model['buy'] = '-' if quote.BidPx is None else quote.BidPx
        model['sell'] = '-' if quote.OfferPx is None else quote.OfferPx
        if quote.Details:
            precision = quote.Details.get('precision')
            model['dc'] = quote.Details.get('dc')
            model['du'] = quote.Details.get('du')
            model['pre_brl'] = quote.Details['pre_brl']
            model['cupom_ccy'] = quote.Details['cupom_ccy']
            model['brl_risk'] = quote.Details.get('brl_risk')
            model['spread_risk'] = quote.Details.get('spread_risk')
            model['spread_notional'] = quote.Details.get('spread_notional')
            model['spread'] = quote.Details.get('spread')
            model['revenue'] = quote.Details.get('revenue_brl')
            model['s_cost'] = round_if_valid(quote.Details.get('s_cost'), precision)
            model['f_cost'] = round_if_valid(quote.Details.get('f_cost'), precision)
            model['fwd_points'] = quote.Details.get('forward_points')
            model['y_ccy'] = quote.Details.get('y_ccy')
            model['y_ccy_client'] = quote.Details.get('y_ccy_client')
            model['f_pfe'] = quote.Details.get('f_pfe')
            model['validate_kyc'] = quote.Details.get('validate_kyc')
            model['validate_isda'] = quote.Details.get('validate_isda')
            model['adj_maturity'] = quote.Details.get('adjusted_maturity')
            model['present_value_ccy'] = quote.Details.get('present_value_ccy')

    elif isinstance(msg, messages.QuoteReject):
        if msg.Origin == messages.RejectOrigin.PRICER:
            model = blotter_generic_reject_response(msg)
        else:
            model = blotter_generic_reject_request(msg)

    elif isinstance(msg, messages.QuoteCancel):
        model = blotter_generic_quote_cancel(msg)

    elif isinstance(msg, messages.ExecAcknowledgmentUnknown):
        model = blotter_generic_exec_ack_unknown(msg)

    elif isinstance(msg, messages.ExecAcknowledgment):
        model = blotter_generic_exec_ack(msg)

    elif isinstance(msg, messages.Quote):
        model = blotter_generic_quote(msg)

        if msg.Details:
            precision = msg.Details.get('precision')
            model['dc'] = msg.Details.get('dc')
            model['du'] = msg.Details.get('du')
            model['pre_brl'] = msg.Details['pre_brl']
            model['cupom_ccy'] = msg.Details['cupom_ccy']
            model['brl_risk'] = msg.Details.get('brl_risk')
            model['spread_risk'] = msg.Details.get('spread_risk')
            model['spread_notional'] = msg.Details.get('spread_notional')
            model['spread'] = msg.Details.get('spread')
            model['revenue'] = msg.Details.get('revenue_brl')
            model['s_cost'] = round_if_valid(msg.Details.get('s_cost'), precision)
            model['f_cost'] = round_if_valid(msg.Details.get('f_cost'), precision)
            model['fwd_points'] = msg.Details.get('forward_points')
            model['y_ccy'] = msg.Details.get('y_ccy')
            model['y_ccy_client'] = msg.Details.get('y_ccy_client')
            model['f_pfe'] = msg.Details.get('f_pfe')
            model['validate_kyc'] = msg.Details.get('validate_kyc')
            model['validate_isda'] = msg.Details.get('validate_isda')
            model['adj_maturity'] = msg.Details.get('adjusted_maturity')
            model['present_value_ccy'] = msg.Details.get('present_value_ccy')

    return model


def update_blotter(msg):
    model = None

    if isinstance(msg, messages.QuoteRequest):
        quoterequest = msg
    else:
        quoterequest, _ = get_quoterequest_msg(msg.QuoteReqID)

    if quoterequest.SecurityType == messages.EnumSecurityType.SPOT:
        model = update_blotter_spot(msg)
        if model:
            cur = model["currency"]
            root_key = f'Balance/SPOT/{cur}/TotalAmount/'
            if model['mtype'] == "DEAL":
                buy_total = sum(float(databus.get(root_key + 'BuyD' + str(i))) for i in range(3))
                sell_total = sum(float(databus.get(root_key + 'SellD' + str(i))) for i in range(3))
                accounting_supplier_model = {
                    model['currency']: {
                        'net': buy_total - sell_total,
                        'buy_total': buy_total,
                        'buy_d0': float(databus.get(root_key + 'BuyD0')),
                        'buy_d1': float(databus.get(root_key + 'BuyD1')),
                        'buy_d2': float(databus.get(root_key + 'BuyD2')),
                        'sell_total': sell_total,
                        'sell_d0': float(databus.get(root_key + 'SellD0')),
                        'sell_d1': float(databus.get(root_key + 'SellD1')),
                        'sell_d2': float(databus.get(root_key + 'SellD2')),
                    }
                }
                accounting_supplier_model_json = json.dumps(json.dumps(accounting_supplier_model))
                r.publish('accounting_fxsupplier', accounting_supplier_model_json)
    elif quoterequest.SecurityType == messages.EnumSecurityType.NDF:
        model = update_blotter_ndf(msg)

    if model:
        model_json = json.dumps(model)
        entry = {model['quote_req_id']: model_json}
        databus.update_from_dict(entry, 'Blotter')
        r.publish('blotter', json.dumps(model_json))
        r.publish('blotter_fxsupplier', json.dumps(model_json))
