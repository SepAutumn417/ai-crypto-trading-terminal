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


class SubmissionFailedException(AppException):
    def __init__(self, plan_id: str, error_code: str, error_message: str, retryable: bool = False, retry_after_seconds: int | None = None):
        details = {
            "plan_id": str(plan_id),
            "error_code": error_code,
            "retryable": retryable,
        }
        if retry_after_seconds is not None:
            details["retry_after_seconds"] = retry_after_seconds
        super().__init__(
            "SUBMISSION_FAILED",
            f"订单提交失败: {error_message}",
            422,
            details=details,
        )


class ExecutionDisabledException(AppException):
    def __init__(self, reason: str):
        super().__init__("EXECUTION_DISABLED", reason, 409)


class IdempotencyConflictException(AppException):
    def __init__(self, plan_id: str, current_status: str):
        super().__init__(
            "IDEMPOTENCY_CONFLICT",
            f"计划 {plan_id} 已在状态 {current_status}，无需重复执行",
            409,
            details={"plan_id": str(plan_id), "current_status": current_status},
        )


class PlanNotRecheckableException(AppException):
    def __init__(self, plan_id: str, current_status: str):
        super().__init__(
            "PLAN_NOT_RECHECKABLE",
            f"计划 {plan_id} 状态 {current_status}，不允许重新检查",
            409,
            details={"plan_id": str(plan_id), "current_status": current_status},
        )