from ingestion.src.handler.validate_handler import ValidateHandler
from ingestion.src.source.bao.model.daily_bar import BaoDailyBar




class BaoValidateHandler(ValidateHandler):
    def __init__(self, config):
        self.config = config

    #校验项目	规则
    #基础字段	股票代码、交易日期不能为空
    #价格	OHLC 不允许负值
    #价格关系	最高价 ≥ 最低价
    #成交量	不允许负数
    #成交金额	不允许负数
    @staticmethod
    def validate(bar:BaoDailyBar):

        if bar.symbol is None or bar.trade_date is None:
                raise ValueError(f"股票代码或交易日期不能为空: {bar}")
        if bar.open < 0 or bar.high < 0 or bar.low < 0 or bar.close < 0:
                raise ValueError(f"OHLC价格不允许负值: {bar}")
        if bar.high < bar.low:
                raise ValueError(f"最高价必须大于等于最低价: {bar}")
        if bar.volume < 0:
                raise ValueError(f"成交量不允许负数: {bar}")
        if bar.amount < 0:
                raise ValueError(f"成交金额不允许负数: {bar}")