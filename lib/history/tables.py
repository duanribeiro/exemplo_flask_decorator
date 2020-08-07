from sqlalchemy import Column, String, Integer, ForeignKey, Time, Date, Float
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from lib.liblog import Bcolors
import os

Base = declarative_base()

RFX_HISTORY_DIR = os.getenv("RFX_HISTORY_DIR")
if RFX_HISTORY_DIR is None:
    print("RFX_HISTORY_DIR env var is not set.")
if RFX_HISTORY_DIR == "":
    print("RFX_HISTORY_DIR string is empty.")


def connect_to_transactions_db():
    transactions_db_filepath = f"{RFX_HISTORY_DIR}/transactions.db"
    transactions_db_sqlite_url = f"sqlite:///{transactions_db_filepath}"
    transactions_db_exists = os.path.exists(transactions_db_filepath)
    engine = create_engine(transactions_db_sqlite_url)
    if not transactions_db_exists:
        try:
            os.makedirs(RFX_HISTORY_DIR, exist_ok=True)
            print(f"Creating {transactions_db_filepath}... ", end="")
            create_transactions_db(engine)
            SessionMaker = sessionmaker(bind=engine)
            print(f"{Bcolors.OKGREEN}OK{Bcolors.END}", flush=True)
        except OSError:
            log_error(f"Creation of the directory failed RFX_HISTORY_DIR: {RFX_HISTORY_DIR}")
    else:
        print(f"Connecting to {transactions_db_filepath}... ", end="")
        SessionMaker = sessionmaker(bind=engine)
        print(f"{Bcolors.OKGREEN}OK{Bcolors.END}", flush=True)

    return SessionMaker


def create_transactions_db(engine, user_version=1):
    Base.metadata.create_all(engine)
    db_conn = engine.connect()
    db_conn.execute(f"PRAGMA user_version = {user_version}")
    db_conn.close()


# Table names
TRANSACTIONS = "Transactions"
QUOTE_REQUESTS = "QuoteRequests"
QUOTES = "Quotes"
QUOTE_REJECTS = "QuoteRejects"
QUOTE_CANCELS = "QuoteCancels"
NEW_ORDERS = "NewOrders"
EXEC_REPORTS = "ExecReports"
EXEC_ACKS = "ExecAcks"
METRICS = "Metrics"


class Transaction(Base):
    __tablename__ = TRANSACTIONS

    quote_req_id = Column(String, primary_key=True)
    customer_id = Column(String)  # CNPJ
    customer_str = Column(String)  # ex: Petrole Bras SA
    customer_deal_code = Column(String)  # ex: PETRO
    currency = Column(String)
    ord_qty = Column(Float)
    status = Column(String)
    fx_product = Column(String)
    revenue_brl = Column(Float, default=0.0)
    transact_date = Column(Date)
    transact_time = Column(Time)

    symbol = Column(String, default=None)
    settlement_ccy = Column(Date, default=None)
    settlement_brl = Column(Date, default=None)
    settlement_ccy_dn = Column(String, default=None)
    settlement_brl_dn = Column(String, default=None)
    maturity = Column(Date, default=None)
    buy = Column(Float, default=None)
    sell = Column(Float, default=None)
    dc = Column(Integer, default=None)
    du = Column(Integer, default=None)
    pre_brl = Column(Float, default=None)
    cupom_ccy = Column(Float, default=None)
    brl_risk = Column(Float, default=None)
    spread_risk = Column(Float, default=None)
    spread_notional = Column(Float, default=None)
    spread = Column(Float, default=None)
    s_cost = Column(Float, default=None)
    f_cost = Column(Float, default=None)
    fwd_points = Column(Float, default=None)
    y_ccy = Column(Float, default=None)
    y_ccy_client = Column(Float, default=None)
    f_pfe = Column(Float, default=None)
    validate_kyc = Column(String, default=None)
    validate_isda = Column(String, default=None)
    adj_maturity = Column(Date, default=None)
    present_value_ccy = Column(Float, default=None)
    reject_text = Column(String, default=None)

    # one to one relationships
    quote_request_rel = relationship("QuoteRequest", uselist=False, back_populates="transaction_rel")
    quote_reject_rel = relationship("QuoteReject", uselist=False, back_populates="transaction_rel")
    quote_cancel_rel = relationship("QuoteCancel", uselist=False, back_populates="transaction_rel")
    exec_ack_rel = relationship("ExecAck", uselist=False, back_populates="transaction_rel")
    exec_report_rel = relationship("ExecReport", uselist=False, back_populates="transaction_rel")
    new_order_rel = relationship("NewOrder", uselist=False, back_populates="transaction_rel")
    metrics_rel = relationship("Metrics", uselist=False, back_populates="transaction_rel")

    # one to many relationship
    quotes = relationship("Quote")

    def __init__(
        self,
        quote_req_id,
        customer_id,
        customer_str,
        customer_deal_code,
        currency,
        ord_qty,
        status,
        fx_product,
        transact_date,
        transact_time,
    ):
        self.quote_req_id = quote_req_id
        self.customer_id = customer_id
        self.customer_str = customer_str
        self.customer_deal_code = customer_deal_code
        self.currency = currency
        self.ord_qty = ord_qty
        self.status = status
        self.fx_product = fx_product
        self.transact_date = transact_date
        self.transact_time = transact_time


class QuoteRequest(Base):
    __tablename__ = QUOTE_REQUESTS

    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"), primary_key=True)
    ccy1_market_type = Column(Integer)
    ccy2_market_type = Column(Integer)
    currency = Column(String)
    customer_deal_code = Column(String)
    customer_id = Column(String)
    customer_str = Column(String)
    details = Column(String)
    fixing_date = Column(String)
    fixing_source = Column(String)
    fut_sett_date = Column(String)
    fut_sett_date_2 = Column(String)
    msg_type = Column(String)
    ord_type = Column(String)
    ord_qty = Column(String)
    ord_qty_2 = Column(String)
    original_str = Column(String)
    security_type = Column(Integer)
    sett_currency = Column(String)
    sett_qualifier = Column(String)
    side = Column(Integer)
    symbol = Column(String)
    tenor_value = Column(String)
    tenor_value_2 = Column(String)
    text = Column(String)
    trade_date = Column(String)
    transact_time = Column(String)

    # one to one relationship
    transaction_rel = relationship("Transaction", back_populates="quote_request_rel", uselist=False)

    def __init__(self, quote_request_obj):
        self.quote_req_id = quote_request_obj.QuoteReqID
        self.ccy1_market_type = quote_request_obj.Ccy1MarketType
        self.ccy2_market_type = quote_request_obj.Ccy2MarketType
        self.currency = quote_request_obj.Currency
        self.customer_deal_code = quote_request_obj.CustomerDealCode
        self.customer_id = quote_request_obj.CustomerID
        self.customer_str = quote_request_obj.CustomerStr
        self.details = quote_request_obj.Details
        self.fixing_date = quote_request_obj.FixingDate
        self.fixing_source = quote_request_obj.FixingSource
        self.fut_sett_date = quote_request_obj.FutSettDate
        self.fut_sett_date_2 = quote_request_obj.FutSettDate2
        self.msg_type = quote_request_obj.MsgType
        self.ord_type = quote_request_obj.OrdType
        self.ord_qty = quote_request_obj.OrderQty
        self.ord_qty_2 = quote_request_obj.OrderQty2
        self.security_type = quote_request_obj.SecurityType
        self.sett_currency = quote_request_obj.SettlCurrency
        self.sett_qualifier = quote_request_obj.SettlQualifier
        self.side = quote_request_obj.Side
        self.symbol = quote_request_obj.Symbol
        self.tenor_value = quote_request_obj.TenorValue
        self.tenor_value_2 = quote_request_obj.TenorValue2
        self.text = quote_request_obj.Text
        self.trade_date = quote_request_obj.TradeDate
        self.transact_time = quote_request_obj.TransactTime
        self.original_str = quote_request_obj.OriginalStr


class Quote(Base):
    __tablename__ = QUOTES

    quote_id = Column(String, primary_key=True)
    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"))
    original_str = Column(String)
    msg_type = Column(String)
    offer_px = Column(String)
    offer_spot_rate = Column(String)
    bid_px = Column(String)
    bid_spot_rate = Column(String)
    details = Column(String)
    revenue_brl = Column(Float)
    transact_time = Column(String)

    def __init__(self, quote_obj):
        self.quote_id = quote_obj.QuoteID
        self.quote_req_id = quote_obj.QuoteReqID
        self.original_str = quote_obj.OriginalStr
        self.msg_type = quote_obj.MsgType
        self.offer_px = quote_obj.OfferPx
        self.offer_spot_rate = quote_obj.OfferSpotRate
        self.bid_px = quote_obj.BidPx
        self.bid_spot_rate = quote_obj.BidSpotRate
        self.details = str(quote_obj.Details)
        self.revenue_brl = quote_obj.Details["revenue_brl"]
        self.transact_time = quote_obj.TransactTime


class QuoteReject(Base):
    __tablename__ = QUOTE_REJECTS

    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"), primary_key=True)
    original_str = Column(String)
    msg_type = Column(String)
    details = Column(String)
    quote_id = Column(String)
    reason = Column(String)
    text = Column(String)  # Reason of the quote rejection
    origin = Column(String)

    transaction_rel = relationship("Transaction", back_populates="quote_reject_rel", uselist=False)

    def __init__(self, quote_reject_obj):
        self.quote_req_id = quote_reject_obj.QuoteReqID
        self.original_str = str(quote_reject_obj.OriginalStr)
        self.msg_type = quote_reject_obj.MsgType
        self.details = str(quote_reject_obj.Details)
        self.quote_id = quote_reject_obj.QuoteID
        self.reason = quote_reject_obj.Reason
        self.text = quote_reject_obj.Text
        self.origin = quote_reject_obj.Origin


class QuoteCancel(Base):
    __tablename__ = QUOTE_CANCELS

    quote_id = Column(String)
    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"), primary_key=True)
    original_str = Column(String)
    msg_type = Column(String)
    details = Column(String)

    transaction_rel = relationship("Transaction", back_populates="quote_cancel_rel", uselist=False)

    def __init__(self, quote_cancel_obj):
        self.quote_id = quote_cancel_obj.QuoteID
        self.quote_req_id = quote_cancel_obj.QuoteReqID
        self.original_str = str(quote_cancel_obj.OriginalStr)
        self.msg_type = quote_cancel_obj.MsgType
        self.details = str(quote_cancel_obj.Details)


class NewOrder(Base):
    __tablename__ = NEW_ORDERS

    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"), primary_key=True)
    original_str = Column(String)
    msg_type = Column(String)
    details = Column(String)
    quote_id = Column(String)
    cl_order_id = Column(String)

    transaction_rel = relationship("Transaction", back_populates="new_order_rel", uselist=False)

    def __init__(self, new_order_obj):
        self.quote_req_id = new_order_obj.QuoteReqID
        self.original_str = new_order_obj.OriginalStr
        self.msg_type = new_order_obj.MsgType
        self.details = str(new_order_obj.Details)
        self.quote_id = new_order_obj.QuoteID
        self.cl_order_id = new_order_obj.ClOrderID


class ExecReport(Base):
    __tablename__ = EXEC_REPORTS

    exec_id = Column(String, primary_key=True)
    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"))
    original_str = Column(String)
    msg_type = Column(String)
    details = Column(String)
    quote_id = Column(String)
    cl_order_id = Column(String)
    order_id = Column(String)
    exec_report_type = Column(String)

    transaction_rel = relationship("Transaction", back_populates="exec_report_rel", uselist=False)

    def __init__(self, exec_report_obj):
        self.exec_id = exec_report_obj.ExecID
        self.quote_req_id = exec_report_obj.QuoteReqID
        self.original_str = exec_report_obj.OriginalStr
        self.msg_type = exec_report_obj.MsgType
        self.details = str(exec_report_obj.Details)
        self.quote_id = exec_report_obj.QuoteID
        self.cl_order_id = exec_report_obj.ClOrderID
        self.order_id = exec_report_obj.OrderID
        self.exec_report_type = exec_report_obj.Type


class ExecAck(Base):
    __tablename__ = EXEC_ACKS

    order_id = Column(String, primary_key=True)
    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"))
    original_str = Column(String)
    msg_type = Column(String)
    details = Column(String)
    quote_id = Column(String)
    cl_order_id = Column(String)
    exec_id = Column(String)

    transaction_rel = relationship("Transaction", back_populates="exec_ack_rel", uselist=False)

    def __init__(self, exec_ack_obj):
        self.order_id = exec_ack_obj.OrderID
        self.quote_req_id = exec_ack_obj.QuoteReqID
        self.original_str = exec_ack_obj.OriginalStr
        self.msg_type = exec_ack_obj.MsgType
        self.details = str(exec_ack_obj.Details)
        self.quote_id = exec_ack_obj.QuoteID
        self.cl_order_id = exec_ack_obj.ClOrderID
        self.exec_id = exec_ack_obj.ExecID


class Metrics(Base):
    __tablename__ = METRICS

    quote_req_id = Column(String, ForeignKey(f"{TRANSACTIONS}.quote_req_id"), primary_key=True)
    timestamps = Column(String)

    # one to one relationship
    transaction_rel = relationship("Transaction", back_populates="metrics_rel", uselist=False)

    def __init__(self, quote_req_id, timestamps):
        self.quote_req_id = quote_req_id
        self.timestamps = timestamps
