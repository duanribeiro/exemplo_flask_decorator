"""
Este arquivo descreve a representação interna das mensagens recebidas dos tradutores.
As classes devem armazenar as informações necessárias para tratamento interno.
"""

import sys
import json
from enum import IntEnum


class EnumSecurityType(IntEnum):
    SPOT = 0
    NDF = 1


class EnumSide(IntEnum):
    TWOWAY = 0
    BUY = 1
    SELL = 2


class MarketType(IntEnum):
    REGULAR = 1
    ONSHORE = 2
    NONDELIVERABLE = 3


class RejectOrigin(IntEnum):
    CLIENT = 1
    PRICER = 2


class ExecReportType(IntEnum):
    ACCEPT = 1
    REJECT = 2


class Code:
    QuoteRequest = "RFQ"
    Quote = "Quote"
    QuoteReject = "Reject"
    QuoteCancel = "Cancel"
    NewOrder = "NewOrder"
    ExecReport_Reject = "ExecReport_Reject"
    ExecReport_Accept = "ExecReport_Accept"
    ExecAck_Unknown = "ExecAck_Unknown"
    ExecAck = "Ack"


Flow = {
    None: [Code.QuoteRequest],
    Code.QuoteRequest: [Code.Quote, Code.QuoteReject],
    Code.Quote: [Code.Quote, Code.NewOrder, Code.QuoteReject, Code.QuoteCancel],
    Code.QuoteReject: [],
    Code.QuoteCancel: [],
    Code.NewOrder: [Code.ExecReport_Accept, Code.ExecReport_Reject],
    Code.ExecReport_Reject: [],
    Code.ExecReport_Accept: [Code.ExecAck, Code.ExecAck_Unknown],
    Code.ExecAck_Unknown: [],
    Code.ExecAck: [],
}


def serialize_to_json(msg):
    return json.dumps(msg.__dict__)


def parse_from_json(strjson):
    attrs = json.loads(strjson)
    ClsType = getattr(sys.modules[__name__], attrs.get("MsgType"))
    msg = ClsType()
    msg.__dict__ = attrs

    return msg


class Details(object):
    """
    Classe utilizada para adição de atributos de maneira dinâmica.
    """

    pass


class BaseMessage(object):
    def __init__(self):
        self.OriginalStr = None  # mensagem original. ex: msg fix.
        self.MsgType = self.__class__.__name__
        self.Details = None

    @classmethod
    def getMsgType(cls):
        return cls.__name__


class QuoteRequest(BaseMessage):
    def __init__(self):
        super().__init__()

        self.CustomerID = None  # CNPJ
        self.CustomerStr = None
        self.CustomerDealCode = None
        self.QuoteReqID = None
        self.SettlQualifier = None
        self.Symbol = None
        self.SecurityType = None
        self.Side = None
        self.OrderQty = None
        self.FutSettDate = None
        self.OrdType = None
        self.FutSettDate2 = None
        self.OrderQty2 = None
        self.Currency = None
        self.TransactTime = None
        self.TenorValue = None
        self.TenorValue2 = None
        self.TradeDate = None
        self.Text = None
        self.SettlCurrency = None
        self.FixingDate = None
        self.FixingSource = None
        self.Ccy1MarketType = None
        self.Ccy2MarketType = None
        self.Ccy1SettlementDU = None
        self.Ccy2SettlementDU = None

    def get_message_id(self):
        return self.QuoteReqID

    def get_message_code(self):
        return Code.QuoteRequest


class QuoteReject(BaseMessage):
    def __init__(self):
        super().__init__()

        self.QuoteReqID = None
        self.QuoteID = None
        self.Reason = None
        self.Text = None
        self.Origin = None

    def get_message_id(self):
        return self.QuoteReqID

    def get_message_code(self):
        return Code.QuoteReject


class QuoteCancel(BaseMessage):
    def __init__(self):
        super().__init__()
        self.QuoteReqID = None
        self.QuoteID = None

    def get_message_id(self):
        return self.QuoteReqID

    def get_message_code(self):
        return Code.QuoteCancel


class Quote(BaseMessage):
    def __init__(self):
        super().__init__()

        self.QuoteReqID = None
        self.QuoteID = None
        self.OfferPx = None
        self.OfferSpotRate = None
        self.BidPx = None
        self.BidSpotRate = None
        self.Details = None
        self.TransactTime = None

    def get_message_id(self):
        return self.QuoteID

    def get_message_code(self):
        return Code.Quote


class NewOrderSingle(BaseMessage):
    def __init__(self):
        super().__init__()

        self.QuoteReqID = None
        self.QuoteID = None
        self.ClOrderID = None

    def get_message_id(self):
        return self.ClOrderID

    def get_message_code(self):
        return Code.NewOrder


class ExecReport(BaseMessage):
    def __init__(self):
        super().__init__()

        self.QuoteReqID = None
        self.QuoteID = None
        self.ClOrderID = None
        self.ExecID = None
        self.OrderID = None
        self.Type = None
        self.TransactTime = None

    def get_message_id(self):
        return self.ExecID

    def get_message_code(self):
        if self.Type == ExecReportType.ACCEPT:
            return Code.ExecReport_Accept
        else:
            return Code.ExecReport_Reject


class ExecAcknowledgmentUnknown(BaseMessage):
    def __init__(self):
        super().__init__()

        self.QuoteReqID = None
        self.QuoteID = None
        self.OrderID = None
        self.ClOrderID = None
        self.ExecID = None

    def get_message_id(self):
        return self.OrderID

    def get_message_code(self):
        return Code.ExecAck_Unknown


class ExecAcknowledgment(BaseMessage):
    def __init__(self):
        super().__init__()

        self.QuoteReqID = None
        self.QuoteID = None
        self.ClOrderID = None
        self.ExecID = None
        self.OrderID = None

    def get_message_id(self):
        return self.OrderID

    def get_message_code(self):
        return Code.ExecAck
