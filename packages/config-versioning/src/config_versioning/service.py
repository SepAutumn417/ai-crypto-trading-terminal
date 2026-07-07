from datetime import datetime, timezone
from uuid import UUID, uuid4
from shared.enums import ConfigType
from config_versioning.models import ConfigVersion


class ConfigNotFoundError(Exception):
    pass


class ConfigStore:
    """内存实现，供单元测试使用。apps/api 用数据库实现替换。"""

    def __init__(self) -> None:
        self._versions: dict[UUID, ConfigVersion] = {}

    def create_version(self, config_type: ConfigType, version_label: str, payload: dict) -> ConfigVersion:
        for v in self._versions.values():
            if v.config_type == config_type and v.version_label == version_label:
                raise ValueError(f"Duplicate version_label: {config_type.value}/{version_label}")
        version = ConfigVersion(
            id=uuid4(), config_type=config_type, version_label=version_label,
            payload=payload, is_active=False,
            created_at=datetime.now(timezone.utc), activated_at=None,
        )
        self._versions[version.id] = version
        return version

    def get_version(self, version_id: UUID) -> ConfigVersion:
        v = self._versions.get(version_id)
        if v is None:
            raise ConfigNotFoundError(f"Version {version_id} not found")
        return v

    def list_versions(self, config_type: ConfigType) -> list[ConfigVersion]:
        return [v for v in self._versions.values() if v.config_type == config_type]

    def activate_version(self, version_id: UUID) -> ConfigVersion:
        target = self.get_version(version_id)
        for v in self._versions.values():
            if v.config_type == target.config_type and v.is_active:
                self._versions[v.id] = v.model_copy(update={"is_active": False})
        activated = target.model_copy(update={
            "is_active": True,
            "activated_at": datetime.now(timezone.utc),
        })
        self._versions[activated.id] = activated
        return activated

    def get_active_version(self, config_type: ConfigType) -> ConfigVersion:
        for v in self._versions.values():
            if v.config_type == config_type and v.is_active:
                return v
        raise ConfigNotFoundError(f"No active version for {config_type.value}")