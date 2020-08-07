#!/usr/bin/env python3

import os
import quickfix as fix
import quickfix44 as fix44
import messages
from libep import log_error
from libutils import get_utc_time
from libdatabus import databus
from libtransactions import get_transaction


class FieldNotFound(Exception):
    pass


class FieldTypeError(Exception):
    pass


def iso_date(strdate):
    """
    Converte data no formato YYYYMMDD para YYYY-MM-DD.
    """
    return "{y}-{m}-{d}".format(y=strdate[0:4], m=strdate[4:6], d=strdate[6:8])


def iso_datetime(strdatetime):
    """
    Converte data no formato YYYYMMDDTIME para YYYY-MM-DD TIME.
    """
    return "{y}-{m}-{d} {time}".format(y=strdatetime[0:4], m=strdatetime[4:6], d=strdatetime[6:8], time=strdatetime[9:])


def cast_security_type(strvalue):
    """
    Converte tipo do instrumento de string para enum.
    """
    if strvalue == "FXSPOT":
        return messages.EnumSecurityType.SPOT
    elif strvalue == "FXNDF":
        return messages.EnumSecurityType.NDF

    raise ValueError(f'Produto inválido: {strvalue}')


def cast_side(strvalue):
    """
    Converte Side de string para enum.
    """
    if strvalue == "0":
        return messages.EnumSide.TWOWAY
    elif strvalue == "1":
        return messages.EnumSide.BUY
    elif strvalue == "2":
        return messages.EnumSide.SELL

    raise ValueError


def cast_market_type(strvalue):
    """
    Converte Martek Type de string para enum.
    """
    if strvalue == "R":
        return messages.MarketType.REGULAR
    elif strvalue == "O":
        return messages.MarketType.ONSHORE
    elif strvalue == "N":
        return messages.MarketType.NONDELIVERABLE

    raise ValueError


def cast_to(variable, type, field=None):
    """
    Tenta converter `variable` para `type`, caso não seja possível lança FieldTypeError.
    """
    try:
        return type(variable)
    except (ValueError, IndexError) as e:
        if field:
            if str(e):
                raise FieldTypeError(str(e))

            raise FieldTypeError("Campo {}, tipo ou valor inválido".format(field))

    return None


def get_field(field, msg, required=False, rtype=None):
    """
    Retorna valor do campo `field` da mensagem `msg`. Se `required` for True, lança  FieldNotFound.
    Faz casting para `rtype` se este estiver definido.
    """
    field_instance = field if isinstance(field, int) else field().getField()

    if msg.isSetField(field_instance):
        value = msg.getField(field)

        if rtype:
            return cast_to(value, rtype, field)

        return value
    elif required:
        raise FieldNotFound("Campo {} não encontrado".format(field))

    return None


def set_field_header(fixmsg, field, value):
    """
    Seta campo do header da mensagem fix, se valor for válido.
    """
    if value is not None:
        fixmsg.getHeader().setField(field(value))


def set_field(fixmsg, field, value):
    """
    Seta campo do corpo da mensagem fix, se valor for válido.
    """
    if value is not None:
        fixmsg.setField(field(value))


def copy_field(source, dest, field, field_dest=None):
    """
    Copia campo @field de uma mensagem fix para outra.
    """

    if isinstance(field, int):
        if source.isSetField(field):
            value = source.getField(field)
            if field_dest:
                dest.setField(field_dest, value)
            else:
                dest.setField(field, value)
    else:
        if source.isSetField(field()):
            field_source_inst = field()
            _ = source.getField(field_source_inst)

            if field_dest:
                field_dest_inst = field_dest(field_source_inst.getValue())
                dest.setField(field_dest_inst)
            else:
                dest.setField(field_source_inst)


def get_customer_party_id(fixmsg):
    group_related_sym = fix44.QuoteRequest().NoRelatedSym()
    group_party_ids = fix44.QuoteRequest().NoRelatedSym().NoPartyIDs()
    fixmsg.getGroup(1, group_related_sym)
    size = int(group_related_sym.getField(453))
    for i in range(size):
        group_related_sym.getGroup(i + 1, group_party_ids)
        if int(group_party_ids.getField(452)) == 13:
            return group_party_ids.getField(448)

    return None


def get_customer_name(cnpj):
    return databus.get("LegalEntities/{cnpj}/CounterpartyName".format(cnpj=cnpj))


def get_contact_info(dealcode=None):
    if dealcode:
        contact = os.getenv(f'CONTACT_INFO_{dealcode}', None)
    else:
        contact = os.getenv('CONTACT_INFO', None)

    if contact:
        return f'{contact}'

    return ''


def fixtomsg_quoterequest(rfq_fix):
    """
    Converte QuoteRequest (fix) para QuoteRequest (message).
    """
    rfq_msg = messages.QuoteRequest()
    rfq_msg.OriginalStr = rfq_fix.toString()

    account = get_field(1, rfq_fix)

    try:
        rfq_msg.CustomerID = account.split()[-1]
    except IndexError:
        log_error('Campo Accont não contém um cliente válido')
        raise FieldNotFound("Campo Accont não contém um cliente válido")

    rfq_msg.CustomerStr = get_customer_name(rfq_msg.CustomerID)
    rfq_msg.CustomerDealCode = get_customer_party_id(rfq_fix)
    rfq_msg.QuoteReqID = get_field(131, rfq_fix, True)
    rfq_msg.SettlQualifier = get_field(22432, rfq_fix)

    group_relatedSym = fix44.QuoteRequest().NoRelatedSym()
    rfq_fix.getGroup(1, group_relatedSym)

    rfq_msg.Symbol = get_field(55, group_relatedSym, True)
    rfq_msg.SecurityType = get_field(167, group_relatedSym, True, cast_security_type)
    rfq_msg.Side = get_field(54, group_relatedSym, True, cast_side)
    rfq_msg.OrderQty = get_field(38, group_relatedSym, True, float)
    rfq_msg.FutSettDate = get_field(64, group_relatedSym, True, iso_date)
    rfq_msg.FutSettDate2 = get_field(193, group_relatedSym, False, iso_date)
    rfq_msg.OrderQty2 = get_field(192, group_relatedSym, False, float)
    rfq_msg.Currency = get_field(15, group_relatedSym)
    rfq_msg.TransactTime = get_field(60, group_relatedSym, True, iso_datetime)
    rfq_msg.TenorValue = get_field(6215, group_relatedSym)
    rfq_msg.TenorValue2 = get_field(6216, group_relatedSym)
    rfq_msg.TradeDate = get_field(75, rfq_fix)
    rfq_msg.Text = get_field(58, rfq_fix)

    rfq_msg.SettlCurrency = get_field(120, rfq_fix)
    rfq_msg.FixingDate = get_field(6203, rfq_fix, False, iso_date)
    rfq_msg.FixingSource = get_field(5974, rfq_fix)
    rfq_msg.Ccy1MarketType = get_field(22159, rfq_fix, False, cast_market_type)
    rfq_msg.Ccy2MarketType = get_field(22160, rfq_fix, False, cast_market_type)

    return rfq_msg


def fixtomsg_newordersingle(newordersingle_fix):
    """
    Converte newordersingle (fix) para newordersingle (message).
    """
    newordersingle_msg = messages.NewOrderSingle()
    newordersingle_msg.OriginalStr = newordersingle_fix.toString()
    newordersingle_msg.QuoteID = get_field(117, newordersingle_fix)
    newordersingle_msg.ClOrderID = get_field(11, newordersingle_fix)
    newordersingle_msg.Price = get_field(44, newordersingle_fix)

    quote, _ = get_transaction(messages.Quote.getMsgType(), newordersingle_msg.QuoteID)
    if quote is None:
        raise RuntimeError(f"Failed to fetch Quote {newordersingle_msg.QuoteID} from databus")
    newordersingle_msg.QuoteReqID = quote.QuoteReqID

    return newordersingle_msg


def fixtomsg_reject(reject_fix):
    """
    Converte reject (fix) para reject (message).
    """
    reject_msg = messages.QuoteReject()
    reject_msg.OriginalStr = reject_fix.toString()
    reject_msg.QuoteReqID = get_field(131, reject_fix)
    reject_msg.QuoteID = get_field(117, reject_fix)
    reject_msg.Reason = get_field(300, reject_fix)
    reject_msg.Text = get_field(58, reject_fix)
    reject_msg.Origin = messages.RejectOrigin.CLIENT
    return reject_msg


def fixtomsg_quoteack(execack_fix):
    """
    Converte exec acknowledge (fix) para exec acknowledge (message).
    """
    exec_ack = messages.ExecAcknowledgment()
    exec_ack.OriginalStr = execack_fix.toString()
    exec_ack.ClOrderID = get_field(11, execack_fix)
    exec_ack.ExecID = get_field(17, execack_fix)
    exec_ack.OrderID = get_field(37, execack_fix)

    exec_report, _ = get_transaction(messages.ExecReport.getMsgType(), exec_ack.ExecID)
    if exec_report is None:
        raise RuntimeError(f"Failed to fetch ExecReport {exec_ack.ExecID} from databus")
    exec_ack.QuoteReqID = exec_report.QuoteReqID
    exec_ack.QuoteID = exec_report.QuoteID

    return exec_ack


def get_quoterequest(quotereq_id):
    """
    Retorna QuoteRequest (message) e QuoteRequest (fix).
    """
    quoterequest_fix = fix.Message()
    quoterequest_msg, _ = get_transaction(messages.QuoteRequest.getMsgType(), quotereq_id)
    if quoterequest_msg is None:
        raise RuntimeError(f"Failed to retrieve QuoteRequest {quotereq_id} from databus")
    quoterequest_fix.setString(quoterequest_msg.OriginalStr)  # NOTE: ñ está utilizando dicionário.
    return quoterequest_msg, quoterequest_fix


def get_newordersingle(clorder_id):
    """
    Retorna NewOrderSingle (message) e NewOrderSingle (fix).
    """
    newordersingle_fix = fix.Message()
    newordersingle_msg, _ = get_transaction(messages.NewOrderSingle.getMsgType(), clorder_id)
    if newordersingle_msg is None:
        raise RuntimeError(f"Failed to retrieve NewOrderSingle {clorder_id} from databus")
    newordersingle_fix.setString(newordersingle_msg.OriginalStr)  # NOTE: ñ está utilizando dicionário.
    return newordersingle_msg, newordersingle_fix


def msgtofix_quote(quote_msg):
    """
    Converte Quote (message) para Quote (fix).
    """
    quoterequest_msg, quoterequest_fix = get_quoterequest(quote_msg.QuoteReqID)

    quote = fix44.Quote()
    quote.reverseRoute(quoterequest_fix.getHeader())

    if quoterequest_msg.SecurityType == messages.EnumSecurityType.SPOT:
        set_field(quote, fix.SecurityType, "FXSPOT")
    elif quoterequest_msg.SecurityType == messages.EnumSecurityType.NDF:
        set_field(quote, fix.SecurityType, "FXNDF")

    set_field(quote, fix.QuoteReqID, quote_msg.QuoteReqID)
    set_field(quote, fix.QuoteID, quote_msg.QuoteID)
    set_field(quote, fix.OfferPx, quote_msg.OfferPx)
    set_field(quote, fix.OfferSpotRate, quote_msg.OfferSpotRate)
    set_field(quote, fix.BidPx, quote_msg.BidPx)
    set_field(quote, fix.BidSpotRate, quote_msg.BidSpotRate)
    set_field(quote, fix.QuoteCondition, "A")
    quote.setField(5082, "2")

    set_field(quote, fix.Symbol, quoterequest_fix.getField(fix.Symbol().getField()))
    set_field(quote, fix.Account, quoterequest_fix.getField(fix.Account().getField()))

    copy_field(quoterequest_fix, quote, fix.FutSettDate)
    copy_field(quoterequest_fix, quote, fix.FutSettDate2)
    copy_field(quoterequest_fix, quote, 6215)
    copy_field(quoterequest_fix, quote, 6216)

    transact_time = fix.TransactTime()
    time_str = get_utc_time().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
    transact_time.setString(time_str)
    quote.setField(transact_time)
    quote_msg.TransactTime = time_str

    if quoterequest_msg.SecurityType == messages.EnumSecurityType.NDF:
        copy_field(quoterequest_fix, quote, fix.OrdType)
        copy_field(quoterequest_fix, quote, fix.TradeDate)
        copy_field(quoterequest_fix, quote, fix.SettlCurrency)

        copy_field(quoterequest_fix, quote, 5974)  # FixingSource
        copy_field(quoterequest_fix, quote, 6203)  # FixingDate

        taker_side = str(quoterequest_fix.getField(fix.Side().getField()))

        if taker_side == '1':
            set_field(quote, fix.OfferForwardPoints, quote_msg.Details.get('forward_points'))
        elif taker_side == '2':
            set_field(quote, fix.BidForwardPoints, quote_msg.Details.get('forward_points'))

    return quote


def msgtofix_cancel(cancel_msg):
    """
    Converte Cancel (message) para Cancel (fix).
    """
    response = fix44.QuoteCancel()
    quoterequest_msg, quoterequest_fix = get_quoterequest(cancel_msg.QuoteReqID)

    response.reverseRoute(quoterequest_fix.getHeader())
    response.setField(fix.QuoteReqID(quoterequest_msg.QuoteReqID))
    response.setField(fix.QuoteID("*"))
    response.setField(fix.QuoteCancelType(1))
    return response


def msgtofix_reject(reject_msg):
    """
    Converte Reject (message) para Reject (fix).
    """
    reject_text = reject_msg.Text

    contact = get_contact_info()
    if contact:
        reject_text += f' ({contact})'

    response = fix44.Message()
    quoterequest_msg, quoterequest_fix = get_quoterequest(reject_msg.QuoteReqID)
    response.reverseRoute(quoterequest_fix.getHeader())
    response.getHeader().setField(fix.MsgType(fix.MsgType_QuoteAcknowledgement))
    response.setField(fix.QuoteReqID(quoterequest_msg.QuoteReqID))
    response.setField(fix.QuoteAckStatus(5))
    response.setField(fix.QuoteRejectReason(99))
    response.setField(fix.Text(reject_text))
    return response


def msgtofix_execreport(execreport_msg):
    """
    Converte ExecReport (message) para ExecReport (fix).
    """
    _, newordersingle_fix = get_newordersingle(execreport_msg.ClOrderID)

    execreport_fix = fix44.ExecutionReport()
    execreport_fix.reverseRoute(newordersingle_fix.getHeader())

    set_field(execreport_fix, fix.ExecID, execreport_msg.ExecID)
    set_field(execreport_fix, fix.OrderID, execreport_msg.OrderID)

    if execreport_msg.Type == messages.ExecReportType.ACCEPT:
        set_field(execreport_fix, fix.ExecType, "2")
        set_field(execreport_fix, fix.OrdStatus, "2")
    else:
        set_field(execreport_fix, fix.ExecType, "8")
        set_field(execreport_fix, fix.OrdStatus, "8")

    set_field(execreport_fix, fix.ExecTransType, "0")

    set_field(execreport_fix, fix.LeavesQty, 0)
    copy_field(newordersingle_fix, execreport_fix, fix.Price, fix.AvgPx)
    copy_field(newordersingle_fix, execreport_fix, fix.OrderQty, fix.CumQty)

    transact_time = fix.TransactTime()
    time_str = get_utc_time().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
    transact_time.setString(time_str)
    execreport_fix.setField(transact_time)
    execreport_msg.TransactTime = time_str

    def copy(field):
        copy_field(newordersingle_fix, execreport_fix, field)

    copy(fix.SecurityType)
    copy(fix.ClOrdID)
    copy(fix.Account)
    copy(fix.Symbol)
    copy(fix.OrderQty)
    copy(fix.Price)
    copy(fix.Side)
    copy(fix.Currency)
    copy(fix.LastSpotRate)
    copy(fix.FutSettDate)
    copy(fix.FutSettDate2)
    copy(6215)  # TenorValue
    copy(6216)  # TenorValue2

    return execreport_fix


def translate_fix_to_msg(fix_obj):
    msg_obj = None
    reject_msg = None
    ignore_msg = None

    msg_type = fix_obj.getHeader().getField(fix.MsgType()).getString()

    if msg_type == "R":
        if fix_obj.getField(5082) != "2":
            reject_msg = "Only manual pricing allowed"
        else:
            try:
                msg_obj = fixtomsg_quoterequest(fix_obj)
            except (FieldNotFound, FieldTypeError) as e:
                reject_msg = str(e)
            except Exception:
                reject_msg = "Invalid quote request"
    elif msg_type == "D":
        try:
            msg_obj = fixtomsg_newordersingle(fix_obj)
        except RuntimeError as e:
            ignore_msg = str(e)
    elif msg_type == "b":
        msg_obj = fixtomsg_reject(fix_obj)
    elif msg_type == "BN":
        try:
            msg_obj = fixtomsg_quoteack(fix_obj)
        except RuntimeError as e:
            ignore_msg = str(e)
    else:
        ignore_msg = f"Received fix message of invalid type {msg_type}"

    return msg_obj, reject_msg, ignore_msg


def translate_msg_to_fix(msg_obj):
    fix_msg = None
    err_msg = None
    try:
        if isinstance(msg_obj, messages.Quote):
            fix_msg = msgtofix_quote(msg_obj)
        elif isinstance(msg_obj, messages.QuoteCancel):
            fix_msg = msgtofix_cancel(msg_obj)
        elif isinstance(msg_obj, messages.QuoteReject):
            fix_msg = msgtofix_reject(msg_obj)
        elif isinstance(msg_obj, messages.ExecReport):
            fix_msg = msgtofix_execreport(msg_obj)
        else:
            err_msg = f"Received message of invalid type {type(msg_obj).__name__}"
    except RuntimeError as e:
        err_msg = str(e)

    return fix_msg, err_msg
