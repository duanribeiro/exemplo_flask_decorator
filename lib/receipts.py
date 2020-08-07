from libdatabus import databus
import messages


def gen_receipt_ndf(quoterequest, quote):
    side_dict = {
        messages.EnumSide.SELL: 'A',  # se cliente está vendendo, banco está comprando
        messages.EnumSide.BUY: 'P',  # se cliente está comprando, banco está vendendo
    }
    side = side_dict.get(quoterequest.Side, 'ERROR')
    codigo_cliente_databus_key = f"Transactions/Messages/QuoteRequest/{quoterequest.QuoteReqID}/GLOB_Client_ID"
    codigo_cliente = databus.get(codigo_cliente_databus_key)
    result = {
        "Transaction_ID": quoterequest.QuoteReqID,
        "Client_CNPJ": quoterequest.CustomerID,
        "Client_ID": codigo_cliente,  # ??? # RESPOSTA GLOB (BIO FICOU DE VERIFICAR)
        "Client_ID2": "",  # ??? # RESPOSTA GLOB (BIO FICOU DE VERIFICAR)
        "StartDate": quoterequest.TradeDate,
        "Maturity": quoterequest.FutSettDate,
        "FixingConvention": quote.Details['dn'],  # EXPLICADO NO DOC
        "Side": side,
        "CurrencyCode_ISO": quoterequest.Currency,
        "Amount_CCY": quoterequest.OrderQty,
        "SPOT_CCY_CostRate": quote.Details['s_cost'],
        "TransactionValue_BRL": quote.Details['value_brl'],  # NOTIONAL * S_COST
        "FWD_CCY_ClientRate": quote.Details['quote'],  # QUOTE
        "FWD_CCY_CostRate": quote.Details['f_cost'],  # F_COST
        "FWD_BRL_Amount": quote.Details['value_brl'],  # NOTIONAL * QUOTE
        "Yield_CCY_ClientRate": quote.Details['y_ccy_client'],  # CUPOM CAMBIAL +- SPREAD IMPLI. PAG. 47
        "Yield_CCY_CostRate": quote.Details['y_ccy'],  # CUPOM CAMBIAL
        "Yield_CCY_Convention": "TAXA_LINEAR_AA_360",
        "Yield_BRL_ClientRate": quote.Details['y_brl'],  # TAXA PRE
        "Yield_BRL_CostRate": quote.Details['y_brl'],  # TAVA PRE
        "Yield_BRL_Convention": "TAXA_OVER_252",
    }

    return result


def gen_receipt_spot(quoterequest, quote):
    bacen_code = databus.get(f'Currencies/{quoterequest.Currency}/CodeBACEN')
    market_type = str(databus.get(f'LegalEntities/{quoterequest.CustomerID}/FXMarketType'))
    default_transaction_type = databus.get(f'LegalEntities/{quoterequest.CustomerID}/DefaultFXTransaction')
    side_dict = {
        messages.EnumSide.SELL: 'A',  # se cliente está vendendo, banco está comprando
        messages.EnumSide.BUY: 'P',  # se cliente está comprando, banco está vendendo
    }
    buy_sell_pt = {messages.EnumSide.SELL: 'VENDA', messages.EnumSide.BUY: 'COMPRA'}
    side = side_dict.get(quoterequest.Side, 'ERROR')
    side_pt = buy_sell_pt.get(quoterequest.Side, 'ERROR')

    transaction_type = default_transaction_type
    settlement_type_brl = ""
    if market_type == "1":  # TODO Improve this case
        if default_transaction_type == "IMPORT_EXPORT":
            transaction_type = "IMPORTACAO_EXPORTACAO"
            settlement_type_brl = ""
        elif default_transaction_type == "FINANCIAL":
            transaction_type = "FINANCEIRO"
            settlement_type_brl = ""
    elif market_type == "2":
        if default_transaction_type == 'INTERBANK_CLEARING':
            transaction_type = f'INTERBANCARIO_{side_pt}_PRONTO_COM_CLEARING'
            settlement_type_brl = 'CAMARA'
        elif default_transaction_type == 'INTERBANK_NO_CLEARING':
            transaction_type = f'INTERBANCARIO_{side_pt}_PRONTO_SEM_CLEARING'
            settlement_type_brl = 'RESERVA'

    result = {
        "Transaction_ID": quoterequest.QuoteReqID,
        "Trading_Day": quoterequest.TradeDate,
        "Client_CNPJ": quoterequest.CustomerID,
        "Client_Name": quoterequest.CustomerStr,
        "MarketType": market_type,
        "Side": side,
        "CurrencyCode_ISO": quoterequest.Currency,
        "CurrencyCode_BACEN": bacen_code,
        "Amount_CCY": quoterequest.OrderQty,
        "Amount_BRL": quote.Details['amount_brl'],
        "Amount_USD": quote.Details['amount_usd'],
        "SPOT_CCY_CostRate": quote.Details['s_cost'],
        "FX_ClientRate": quote.Details['quote'],
        "USD_Parity": quote.Details['usdbrl_quote'],
        "SettlementDate_CCY": quote.Details['settlement_date_ccy'],
        "SettlementDate_BRL": quote.Details['settlement_date_brl'],
        "Transaction_Type": transaction_type,
        "SettlementType_BRL": settlement_type_brl,
    }

    return result
