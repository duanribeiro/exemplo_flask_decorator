#!/usr/bin/env python3

import lib.messages as messages
import json
import datetime
from lib.history import tables
from lib.libutils import get_local_time
from sqlalchemy import func
from sqlalchemy import desc
from lib.libdatabus import databus


def insert_transaction(j_transaction, session):
    msgtype = j_transaction["MsgType"]
    if msgtype == "QuoteRequest":
        j_transaction["Status"] = messages.Code.QuoteRequest
        insert_QuoteRequest(j_transaction, session)
    elif msgtype == "Quote":
        j_transaction["Status"] = messages.Code.Quote
        insert_Quote(j_transaction, session)
    elif msgtype == "QuoteReject":
        j_transaction["Status"] = messages.Code.QuoteReject
        insert_QuoteReject(j_transaction, session)
    elif msgtype == "QuoteCancel":
        j_transaction["Status"] = messages.Code.QuoteCancel
        insert_QuoteCancel(j_transaction, session)
    elif msgtype == "NewOrderSingle":
        j_transaction["Status"] = messages.Code.NewOrder
        insert_NewOrder(j_transaction, session)
    elif msgtype == "ExecReport":
        if j_transaction["Type"] == messages.ExecReportType.ACCEPT:
            j_transaction["Status"] = messages.Code.ExecReport_Accept
        elif j_transaction["Type"] == messages.ExecReportType.REJECT:
            j_transaction["Status"] = messages.Code.ExecReport_Reject
        else:
            j_transaction["Status"] = "Undefined"
        insert_ExecReport(j_transaction, session)
    elif msgtype == "ExecAck_Unknown":
        j_transaction["Status"] = messages.Code.ExecAck_Unknown
        insert_ExecAck(j_transaction, session)
    elif msgtype == "ExecAcknowledgment":
        j_transaction["Status"] = messages.Code.ExecAck
        insert_ExecAck(j_transaction, session)
    else:
        pass


def insert_transaction_message(j_transaction, session):
    quote_req_id = j_transaction["QuoteReqID"]
    customer_id = j_transaction["CustomerID"]
    customer_str = j_transaction["CustomerStr"]
    customer_deal_code = j_transaction["CustomerDealCode"]
    currency = j_transaction["Currency"]
    ord_qty = j_transaction["OrderQty"]
    status = j_transaction["MsgType"]
    security_type = j_transaction["SecurityType"]
    if security_type == 0:
        fx_product = "SPOT"
    elif security_type == 1:
        fx_product = "NDF"
    else:
        raise RuntimeError("FX Product not defined.")
        fx_product = "Not Defined"
    transact_datetime = datetime.datetime.strptime(j_transaction["TransactTime"], "%Y-%m-%d %H:%M:%S")
    transact_date = transact_datetime.date()
    transact_time = transact_datetime.time()
    transaction = tables.Transaction(
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
    )
    session.add(transaction)
    session.commit()


def insert_QuoteRequest(j_transaction, session):
    insert_transaction_message(j_transaction, session)
    quote_request_msg = messages.parse_from_json(json.dumps(j_transaction))
    quote_request = tables.QuoteRequest(quote_request_msg)
    session.add(quote_request)
    session.commit()
    quote_req_id = quote_request.quote_req_id
    update_transaction_with_blotter_like_info(session, quote_req_id)


def insert_Quote(j_transaction, session):
    update_transaction(j_transaction, session)
    quote_msg = messages.parse_from_json(json.dumps(j_transaction))
    quote = tables.Quote(quote_msg)
    session.add(quote)
    session.commit()


def insert_QuoteReject(j_transaction, session):
    update_transaction(j_transaction, session)
    quote_reject_msg = messages.parse_from_json(json.dumps(j_transaction))
    quote_reject = tables.QuoteReject(quote_reject_msg)
    session.add(quote_reject)
    session.commit()
    quote_req_id = quote_reject.quote_req_id
    update_transaction_with_blotter_like_info(session, quote_req_id)


def insert_QuoteCancel(j_transaction, session):
    update_transaction(j_transaction, session)
    quote_cancel_msg = messages.parse_from_json(json.dumps(j_transaction))
    quote_cancel = tables.QuoteCancel(quote_cancel_msg)
    session.add(quote_cancel)
    session.commit()
    quote_req_id = quote_cancel.quote_req_id
    update_transaction_with_blotter_like_info(session, quote_req_id)


def insert_NewOrder(j_transaction, session):
    update_transaction(j_transaction, session)
    new_order_msg = messages.parse_from_json(json.dumps(j_transaction))
    new_order = tables.NewOrder(new_order_msg)
    session.add(new_order)
    session.commit()
    quote_req_id = new_order.quote_req_id
    update_transaction_with_blotter_like_info(session, quote_req_id)


def insert_ExecReport(j_transaction, session):
    update_transaction(j_transaction, session)
    exec_report_msg = messages.parse_from_json(json.dumps(j_transaction))
    exec_report = tables.ExecReport(exec_report_msg)
    session.add(exec_report)
    session.commit()
    quote_req_id = exec_report.quote_req_id
    update_transaction_with_blotter_like_info(session, quote_req_id)


def insert_ExecAck(j_transaction, session):
    update_transaction(j_transaction, session)
    exec_ack_msg = messages.parse_from_json(json.dumps(j_transaction))
    exec_ack = tables.ExecAck(exec_ack_msg)
    session.add(exec_ack)
    session.commit()

    revenue_brl = 0.0
    quote_req_id = exec_ack.quote_req_id
    quote_id = exec_ack.quote_id
    quote = session.query(tables.Quote).filter_by(quote_id=quote_id).first()
    if quote:
        revenue_brl = quote.revenue_brl
    update_transaction_column(session, quote_req_id, "revenue_brl", revenue_brl)
    update_transaction_with_blotter_like_info(session, quote_req_id)


def update_transaction_with_blotter_like_info(session, quote_req_id):
    q = session.query(tables.Transaction).filter_by(quote_req_id=quote_req_id).first()
    if q is not None:
        fx_product = q.fx_product
        blotter_info = json.loads(databus.get_dict(f"Blotter/{quote_req_id}"))
        blotter_info_keys = blotter_info.keys()
        if "symbol" in blotter_info_keys:
            symbol = blotter_info["symbol"]
            update_transaction_column(session, quote_req_id, "symbol", symbol)
        if "buy" in blotter_info_keys:
            buy = blotter_info["buy"]
            if isinstance(buy, float):
                update_transaction_column(session, quote_req_id, "buy", buy)
        if "sell" in blotter_info_keys:
            sell = blotter_info["sell"]
            if isinstance(sell, float):
                update_transaction_column(session, quote_req_id, "sell", sell)
        if "spread" in blotter_info_keys:
            spread = blotter_info["spread"]
            update_transaction_column(session, quote_req_id, "spread", spread)
        if "s_cost" in blotter_info_keys:
            s_cost = blotter_info["s_cost"]
            update_transaction_column(session, quote_req_id, "s_cost", s_cost)
        if "validate_kyc" in blotter_info_keys:
            validate_kyc = blotter_info["validate_kyc"]
            update_transaction_column(session, quote_req_id, "validate_kyc", validate_kyc)
        if "rejected_text" in blotter_info.keys():
            reject_text = blotter_info["rejected_text"]
            update_transaction_column(session, quote_req_id, "reject_text", reject_text)

        if fx_product == "SPOT":
            # client_side = blotter_info["client_side"]
            if "settlement_ccy" in blotter_info_keys:
                settlement_ccy = datetime.datetime.strptime(blotter_info["settlement_ccy"], "%Y-%m-%d").date()
                update_transaction_column(session, quote_req_id, "settlement_ccy", settlement_ccy)
            if "settlement_brl" in blotter_info_keys:
                settlement_brl = datetime.datetime.strptime(blotter_info["settlement_brl"], "%Y-%m-%d").date()
                update_transaction_column(session, quote_req_id, "settlement_brl", settlement_brl)
            if "settlement_ccy_dn" in blotter_info_keys:
                settlement_ccy_dn = blotter_info["settlement_ccy_dn"]
                update_transaction_column(session, quote_req_id, "settlement_ccy_dn", settlement_ccy_dn)
            if "settlement_brl_dn" in blotter_info_keys:
                settlement_brl_dn = blotter_info["settlement_brl_dn"]
                update_transaction_column(session, quote_req_id, "settlement_brl_dn", settlement_brl_dn)
            # timestamp = blotter_info["timestamp"]
            # revenue = blotter_info["revenue"]
        elif fx_product == "NDF":
            if "maturity" in blotter_info_keys:
                maturity = datetime.datetime.strptime(blotter_info["maturity"], "%Y-%m-%d").date()
                update_transaction_column(session, quote_req_id, "maturity", maturity)
            if "dc" in blotter_info_keys:
                dc = blotter_info["dc"]
                update_transaction_column(session, quote_req_id, "dc", dc)
            if "du" in blotter_info_keys:
                du = blotter_info["du"]
                update_transaction_column(session, quote_req_id, "du", du)
            if "pre_brl" in blotter_info_keys:
                pre_brl = blotter_info["pre_brl"]
                update_transaction_column(session, quote_req_id, "pre_brl", pre_brl)
            if "cupom_ccy" in blotter_info_keys:
                cupom_ccy = blotter_info["cupom_ccy"]
                update_transaction_column(session, quote_req_id, "cupom_ccy", cupom_ccy)
            if "brl_risk" in blotter_info_keys:
                brl_risk = blotter_info["brl_risk"]
                update_transaction_column(session, quote_req_id, "brl_risk", brl_risk)
            if "spread_risk" in blotter_info_keys:
                spread_risk = blotter_info["spread_risk"]
                update_transaction_column(session, quote_req_id, "spread_risk", spread_risk)
            if "spread_notional" in blotter_info_keys:
                spread_notional = blotter_info["spread_notional"]
                update_transaction_column(session, quote_req_id, "spread_notional", spread_notional)
            if "f_cost" in blotter_info_keys:
                f_cost = blotter_info["f_cost"]
                update_transaction_column(session, quote_req_id, "f_cost", f_cost)
            if "fwd_points" in blotter_info_keys:
                fwd_points = blotter_info["fwd_points"]
                update_transaction_column(session, quote_req_id, "fwd_points", fwd_points)
            if "y_ccy" in blotter_info_keys:
                y_ccy = blotter_info["y_ccy"]
                update_transaction_column(session, quote_req_id, "y_ccy", y_ccy)
            if "y_ccy_client" in blotter_info_keys:
                y_ccy_client = blotter_info["y_ccy_client"]
                update_transaction_column(session, quote_req_id, "y_ccy_client", y_ccy_client)
            if "f_pfe" in blotter_info_keys:
                f_pfe = blotter_info["f_pfe"]
                update_transaction_column(session, quote_req_id, "f_pfe", f_pfe)
            if "validate_isda" in blotter_info_keys:
                validate_isda = blotter_info["validate_isda"]
                update_transaction_column(session, quote_req_id, "validate_isda", validate_isda)
            if "adj_maturity" in blotter_info_keys:
                adj_maturity = datetime.datetime.strptime(blotter_info["adj_maturity"], "%Y-%m-%d").date()
                update_transaction_column(session, quote_req_id, "adj_maturity", adj_maturity)
            if "present_value_ccy" in blotter_info_keys:
                present_value_ccy = blotter_info["present_value_ccy"]
                update_transaction_column(session, quote_req_id, "present_value_ccy", present_value_ccy)
        else:
            pass


def update_transaction(j_transaction, session):
    quote_req_id = j_transaction["QuoteReqID"]
    status = j_transaction["Status"]
    update_transaction_status(session, quote_req_id, status)


def update_transaction_column(session, quote_req_id, column_name, value):
    session.query(tables.Transaction).filter(tables.Transaction.quote_req_id == quote_req_id).update(
        {column_name: value}
    )
    session.commit()


def update_transaction_status(session, quote_req_id, status):
    update_transaction_column(session, quote_req_id, "status", status)


def insert_metrics(j_metrics, msg_id, session):
    msg_id_exists = session.query(
        session.query(tables.Metrics).filter(tables.Metrics.quote_req_id == msg_id).exists()
    ).scalar()
    if msg_id_exists:
        update_timestamps(session, j_metrics, msg_id)
    else:
        insert_timestamps(session, j_metrics, msg_id)


def insert_timestamps(session, j_metrics, msg_id):
    quote_req_id = msg_id
    timestamps = str(j_metrics)
    metrics = tables.Metrics(quote_req_id, timestamps)
    session.add(metrics)
    session.commit()


def update_timestamps(session, j_metrics, msg_id):
    timestamps = str(j_metrics)
    session.query(tables.Metrics).filter(tables.Metrics.quote_req_id == msg_id).update({"timestamps": timestamps})
    session.commit()


def get_number_RFQs_month(session, fx_product):
    today = get_local_time()
    number_RFQs_month = (
        session.query(tables.Transaction)
        .filter_by(fx_product=fx_product)
        .filter(tables.Transaction.transact_date.like(f"%-{today.month:02d}-%"))
        .count()
    )

    return number_RFQs_month


def get_number_recent_RFQs(session, fx_product, number_days_before_today):
    today = get_local_time().date()
    range_days = datetime.timedelta(days=number_days_before_today)
    past_date = today - range_days
    number_recent_RFQs = (
        session.query(tables.Transaction)
        .filter_by(fx_product=fx_product)
        .filter(tables.Transaction.transact_date > past_date)
        .count()
    )

    return number_recent_RFQs


def get_distinct_transact_dates(session, fx_product):
    distinct_transact_dates_query = (
        session.query(tables.Transaction.transact_date).filter_by(fx_product=fx_product).distinct().all()
    )

    distinct_transact_dates = []
    for t in distinct_transact_dates_query:
        for transact_date in t:
            distinct_transact_dates.append(transact_date.strftime("%Y-%m-%d"))

    return distinct_transact_dates


def get_number_RFQs(session, rfq_type, fx_product, transact_date):
    if rfq_type == "all":
        possible_transaction_status = [
            messages.Code.QuoteRequest,
            messages.Code.QuoteCancel,
            messages.Code.Quote,
            messages.Code.NewOrder,
            messages.Code.ExecReport_Reject,
            messages.Code.ExecReport_Accept,
            messages.Code.QuoteReject,
            messages.Code.ExecAck_Unknown,
            messages.Code.ExecAck,
        ]

    elif rfq_type == "deal":
        possible_transaction_status = [messages.Code.ExecAck]
    elif rfq_type == "rejected":
        possible_transaction_status = [messages.Code.ExecReport_Reject, messages.Code.QuoteReject]
    elif rfq_type == "lost":
        possible_transaction_status = [
            messages.Code.QuoteCancel,
            messages.Code.QuoteRequest,
            messages.Code.Quote,
            messages.Code.NewOrder,
            messages.Code.ExecAck_Unknown,
        ]
    else:
        return None

    number_RFQs = (
        session.query(tables.Transaction)
        .filter_by(fx_product=fx_product)
        .filter(tables.Transaction.transact_date.like(transact_date))
        .filter(tables.Transaction.status.in_(possible_transaction_status))
        .count()
    )

    return number_RFQs


def get_ccy_amount(session, ccy, fx_product, transact_date):
    ccy_amount = (
        session.query(func.sum(tables.Transaction.ord_qty))
        .filter_by(fx_product=fx_product, currency=ccy, transact_date=transact_date, status=messages.Code.ExecAck)
        .scalar()
    )

    return ccy_amount


def get_daily_revenue(session, fx_product, transact_date):
    daily_revenue = (
        session.query(func.sum(tables.Transaction.revenue_brl))
        .filter_by(fx_product=fx_product, transact_date=transact_date)
        .scalar()
    )

    return daily_revenue


def get_most_active_counterparts(session, fx_product, transact_date):
    query_most_active_cp = (
        session.query(
            tables.Transaction.customer_deal_code,
            tables.Transaction.customer_str,
            tables.Transaction.customer_id,
            func.sum(tables.Transaction.revenue_brl).label("revenue"),
        )
        .filter_by(fx_product=fx_product, transact_date=transact_date)
        .group_by(tables.Transaction.customer_id)
        .order_by(desc("revenue"))
        .limit(5)  # return only n results
        .all()
    )

    most_active_counterparts = []
    for cp in query_most_active_cp:
        cp_dict = {}
        cp_dict["customer_deal_code"] = cp[0]
        cp_dict["customer_str"] = cp[1]
        cp_dict["customer_id"] = cp[2]
        cp_dict["revenue_brl"] = cp[3]
        most_active_counterparts.append(cp_dict)

    return most_active_counterparts


def get_day_reject_info(session, fx_product, transact_date):
    query = (
        session.query(
            tables.Transaction.quote_req_id,
            tables.Transaction.transact_time,
            tables.Transaction.customer_deal_code,
            tables.Transaction.customer_str,
            tables.Transaction.customer_id,
            tables.QuoteReject.text,
        )
        .filter_by(fx_product=fx_product, transact_date=transact_date, status=messages.Code.QuoteReject)
        .filter(tables.Transaction.quote_req_id == tables.QuoteReject.quote_req_id)
        .order_by("transact_time")
        .all()
    )

    day_reject_info_list = []
    for transaction in query:
        transact_reject_info = {}
        transact_reject_info["deal_id"] = transaction[0]
        transact_reject_info["transact_time"] = transaction[1].strftime("%H:%M:%S")
        transact_reject_info["customer_deal_code"] = transaction[2]
        transact_reject_info["customer_str"] = transaction[3]
        transact_reject_info["customer_id"] = transaction[4]
        transact_reject_info["reject_reason"] = transaction[5]
        day_reject_info_list.append(transact_reject_info)

    return day_reject_info_list


def get_day_trade_info(session, fx_product, transact_date, currencies):
    day_trade_info = {"transact_date": transact_date}
    day_trade_info["number_RFQs_total"] = get_number_RFQs(session, "all", fx_product, transact_date)
    day_trade_info["number_RFQs_deal"] = get_number_RFQs(session, "deal", fx_product, transact_date)
    day_trade_info["number_RFQs_rejected"] = get_number_RFQs(session, "rejected", fx_product, transact_date)
    day_trade_info["number_RFQs_lost"] = get_number_RFQs(session, "lost", fx_product, transact_date)
    day_trade_info["daily_revenue"] = get_daily_revenue(session, fx_product, transact_date)
    for ccy in currencies:
        ccy_amount = f"{ccy}_amount"
        day_trade_info[ccy_amount] = get_ccy_amount(session, ccy, fx_product, transact_date)
    day_trade_info["most_active_counterparts"] = get_most_active_counterparts(session, fx_product, transact_date)

    return day_trade_info


def get_daily_stats(session, fx_product, currencies):
    today = get_local_time().date()
    distinct_transact_dates = get_distinct_transact_dates(session, fx_product)

    for transact_date in distinct_transact_dates:
        transact_date_dateobj = datetime.datetime.strptime(transact_date, "%Y-%m-%d").date()
        if transact_date_dateobj > today:
            distinct_transact_dates.remove(transact_date)

    distinct_transact_dates.sort()

    daily_trade_info = []
    for transact_date in distinct_transact_dates:
        day_trade_info = get_day_trade_info(session, fx_product, transact_date, currencies)
        daily_trade_info.append(day_trade_info)

    daily_stats = {}
    daily_stats["number_RFQs_total"] = get_number_RFQs(session, "all", fx_product, "%")
    daily_stats["number_RFQs_month"] = get_number_RFQs_month(session, fx_product)
    daily_stats["number_RFQs_last_5_days"] = get_number_recent_RFQs(session, fx_product, 5)
    daily_stats["number_RFQs_last_10_days"] = get_number_recent_RFQs(session, fx_product, 10)
    daily_stats["number_RFQs_last_30_days"] = get_number_recent_RFQs(session, fx_product, 30)
    daily_stats["daily_trade_info"] = daily_trade_info

    return daily_stats


def get_transactions_report(session, fx_product, start_date, end_date):
    query = (
        session.query(tables.Transaction)
        .filter_by(fx_product=fx_product)
        .filter(tables.Transaction.transact_date >= start_date)
        .filter(tables.Transaction.transact_date <= end_date)
        .all()
    )

    if fx_product == "SPOT":
        transactions_keys = [
            "quote_req_id",
            "customer_id",
            "customer_str",
            "customer_deal_code",
            "currency",
            "ord_qty",
            "status",
            "fx_product",
            "revenue_brl",
            "symbol",
            "buy",
            "sell",
            "spread",
            "s_cost",
            "validate_kyc",
            "reject_text",
            "settlement_ccy",
            "settlement_brl",
            "settlement_ccy_dn",
            "settlement_brl_dn",
        ]

        transaction_list = []
        for transaction in query:
            transaction_dict = transaction.__dict__
            transaction_dict_out = {}
            for key in transactions_keys:
                transaction_dict_out[key] = transaction_dict[key]
            transact_date = transaction_dict["transact_date"]
            transact_time = transaction_dict["transact_time"]
            transact_datetime_str = f"{transact_date} {transact_time}"
            transact_datetime = datetime.datetime.strptime(transact_datetime_str, "%Y-%m-%d %H:%M:%S")
            transaction_dict_out["transact_datetime"] = transact_datetime

            transaction_list.append(transaction_dict_out)

        csv_columns_dict = {
            "Data de Fechamento": "transact_datetime",
            "Status": "status",
            "Motivo": "reject_text",
            "CNPJ": "customer_id",
            "Cliente": "customer_str",
            "Produto": "fx_product",
            "Moeda": "currency",
            "Volume ME": "ord_qty",
            "TIR": "s_cost",
            "MN": "settlement_brl_dn",
            "ME": "settlement_ccy_dn",
        }

        # Filtering transaction_list to contain only certain keys
        transaction_report = []
        for transaction in transaction_list:
            transaction_new = {}
            for csv_column, csv_column_val in csv_columns_dict.items():
                transaction_new[csv_column] = transaction[csv_column_val]

            if transaction["buy"]:
                transaction_new["Taxa FX"] = transaction["buy"]
            elif transaction["sell"]:
                transaction_new["Taxa FX"] = transaction["sell"]
            else:
                pass

            transaction_report.append(transaction_new)

        column_names = [
            "Data de Fechamento",
            "Status",
            "Motivo",
            "CNPJ",
            "Cliente",
            "Produto",
            "Moeda",
            "Volume ME",
            "Taxa FX",
            "TIR",
            "MN",
            "ME",
        ]

    elif fx_product == "NDF":
        transactions_keys = [
            "quote_req_id",
            "customer_id",
            "customer_str",
            "customer_deal_code",
            "currency",
            "ord_qty",
            "status",
            "fx_product",
            "revenue_brl",
            "symbol",
            "buy",
            "sell",
            "spread",
            "s_cost",
            "validate_kyc",
            "reject_text",
            "maturity",
            "dc",
            "du",
            "pre_brl",
            "cupom_ccy",
            "brl_risk",
            "spread_risk",
            "spread_notional",
            "f_cost",
            "fwd_points",
            "y_ccy",
            "y_ccy_client",
            "f_pfe",
            "validate_isda",
            "adj_maturity",
            "present_value_ccy",
        ]

        transaction_list = []
        for transaction in query:
            transaction_dict = transaction.__dict__
            transaction_dict_out = {}
            for key in transactions_keys:
                transaction_dict_out[key] = transaction_dict[key]
            transact_date = transaction_dict["transact_date"]
            transact_time = transaction_dict["transact_time"]
            transact_datetime_str = f"{transact_date} {transact_time}"
            transact_datetime = datetime.datetime.strptime(transact_datetime_str, "%Y-%m-%d %H:%M:%S")
            transaction_dict_out["transact_datetime"] = transact_datetime

            transaction_list.append(transaction_dict_out)

        # Auxiliary dictionary to construct the NDF report
        csv_columns_dict = {
            "Data Batimento": "transact_datetime",
            "Data Vencimento": "maturity",
            "Status": "status",
            "Motivo": "reject_text",
            "CNPJ": "customer_id",
            "Cliente": "customer_str",
            "Produto": "fx_product",
            "Prazo DC": "dc",
            "Moeda 1 / Referência": "currency",
            "Valor Futuro na Moeda 1": "ord_qty",
            "Pronto Moeda 2 / Moeda 1 - TIR": "s_cost",
            "Pronto Moeda 2 / Moeda 1 - Taxa Client": "s_cost",
            "TIR Moeda 1": "y_ccy",
            "Taxa Moeda 1": "y_ccy_client",
            "TIR Moeda 2": "pre_brl",
            "Taxa Moeda 2": "pre_brl",
            "NDF Moeda 2 / Moeda 1 TIR": "f_cost",
        }

        # Constructing an array with dictionaries containing the informations about the transitions to be reported
        transaction_report = []
        for transaction in transaction_list:
            transaction_new = {}
            for csv_column_key, csv_column_val in csv_columns_dict.items():
                transaction_new[csv_column_key] = transaction[csv_column_val]

            transaction_new["Formato Taxa Moeda 1"] = "LINEAR A.A. (360)"
            transaction_new["Formato Taxa Moeda 2"] = "TAXA OVER 252"
            transaction_new["Moeda 2 / Cotada"] = "BRL"

            if transaction["buy"]:
                transaction_new["Compra/Venda Moeda 1"] = "Compra"
                transaction_new["Compra/Venda Moeda 2"] = "Venda"
                transaction_new["NDF Moeda 2 / Moeda 1 Taxa Cliente"] = transaction["buy"]
            elif transaction["sell"]:
                transaction_new["Compra/Venda Moeda 1"] = "Venda"
                transaction_new["Compra/Venda Moeda 2"] = "Compra"
                transaction_new["NDF Moeda 2 / Moeda 1 Taxa Cliente"] = transaction["sell"]
            else:
                pass

            transaction_report.append(transaction_new)

        column_names = [
            "Data Batimento",
            "Data Vencimento",
            "Status",
            "Motivo",
            "CNPJ",
            "Cliente",
            "Produto",
            "Prazo DC",
            "Compra/Venda Moeda 1",
            "Moeda 1 / Referência",
            "Compra/Venda Moeda 2",
            "Moeda 2 / Cotada",
            "Valor Futuro na Moeda 1",
            "Pronto Moeda 2 / Moeda 1 - TIR",
            "Pronto Moeda 2 / Moeda 1 - Taxa Client",
            "TIR Moeda 1",
            "Taxa Moeda 1",
            "Formato Taxa Moeda 1",
            "TIR Moeda 2",
            "Taxa Moeda 2",
            "Formato Taxa Moeda 2",
            "NDF Moeda 2 / Moeda 1 TIR",
            "NDF Moeda 2 / Moeda 1 Taxa Cliente",
        ]

    else:
        return

    return column_names, transaction_report
