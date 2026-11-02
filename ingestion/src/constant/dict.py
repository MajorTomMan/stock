STOCK_FIELDS = {
    # 公共日线字段
    "basic": {
        # 基础信息
        "trade_date": "trade_date",
        "symbol": "symbol",

        # 价格信息
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "pre_close": "pre_close",

        # 成交信息
        "volume": "volume",
        "amount": "amount",
        "pct_change": "pct_change",
    },

    # BaoStock 数据源字段映射
    "bao": {
        # 基础信息
        "trade_date": "date",
        "symbol": "code",

        # 价格信息
        "pre_close": "preclose",

        # 成交信息
        "pct_change": "pctChg",
        "turnover_rate": "turn",

        # 复权信息
        "adjust_flag": "adjustflag",

        # 交易状态
        "trade_status": "tradestatus",
        "is_st": "isST",

        # 估值指标
        "pe_ttm": "peTTM",
        "pb_mrq": "pbMRQ",
        "ps_ttm": "psTTM",
        "pcf_ncf_ttm": "pcfNcfTTM",
    },
}