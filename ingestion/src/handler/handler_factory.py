from ingestion.src.source.bao.handler.deduplicate_handler import BaoDeduplicateHandler
from ingestion.src.source.bao.handler.validate_handler import BaoValidateHandler


class HandlerFactory:

    _handlers = {
        "bao": {
            "deduplicate": BaoDeduplicateHandler,
            "validate": BaoValidateHandler,
        },
    }

    @classmethod
    def get(cls, source: str, handler_type: str):
        handlers = cls._handlers.get(source)

        if handlers is None:
            raise ValueError(f"不支持的数据源: {source}")

        handler_class = handlers.get(handler_type)

        if handler_class is None:
            raise ValueError(f"不支持的处理器类型: {handler_type}")

        return handler_class(config={})