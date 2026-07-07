from fastapi import HTTPException


class AppException(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details})


class ConfigNotFoundException(AppException):
    def __init__(self, config_type: str):
        super().__init__("CONFIG_NOT_FOUND", f"配置 {config_type} 未找到激活版本", 404)


class PlanNotFoundException(AppException):
    def __init__(self, plan_id: str):
        super().__init__("PLAN_NOT_FOUND", f"计划 {plan_id} 不存在", 404)


class PlanStatusException(AppException):
    def __init__(self, plan_id: str, current: str, expected: str):
        super().__init__("PLAN_STATUS_ERROR", f"计划 {plan_id} 状态 {current}，期望 {expected}", 409)