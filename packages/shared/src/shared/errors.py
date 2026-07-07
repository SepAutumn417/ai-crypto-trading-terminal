class RiskBlockError(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__(f"Risk blocked: {', '.join(reasons)}")


class ConfigNotFoundError(Exception):
    pass


class PlanNotFoundError(Exception):
    pass


class PlanStatusError(Exception):
    pass
