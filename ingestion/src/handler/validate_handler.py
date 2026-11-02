from ingestion.src.model.daily_bar import DailyBar


class ValidateHandler:
    def validate(self, data: list[DailyBar]):
        raise NotImplementedError