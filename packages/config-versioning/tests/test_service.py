from decimal import Decimal
from uuid import uuid4
import pytest
from shared.enums import ConfigType
from config_versioning.service import ConfigStore, ConfigNotFoundError


@pytest.fixture
def store():
    return ConfigStore()


def test_create_version(store):
    v = store.create_version(ConfigType.RISK, "risk-v1", {"max_leverage": 10})
    assert v.config_type == ConfigType.RISK
    assert v.version_label == "risk-v1"
    assert v.is_active is False


def test_activate_version(store):
    v1 = store.create_version(ConfigType.RISK, "risk-v1", {})
    store.activate_version(v1.id)
    assert store.get_version(v1.id).is_active is True

    v2 = store.create_version(ConfigType.RISK, "risk-v2", {})
    store.activate_version(v2.id)
    assert store.get_version(v1.id).is_active is False
    assert store.get_version(v2.id).is_active is True


def test_get_active_version(store):
    v1 = store.create_version(ConfigType.RISK, "risk-v1", {})
    store.activate_version(v1.id)
    assert store.get_active_version(ConfigType.RISK).id == v1.id


def test_get_active_none_raises(store):
    store.create_version(ConfigType.RISK, "risk-v1", {})
    with pytest.raises(ConfigNotFoundError):
        store.get_active_version(ConfigType.RISK)


def test_list_versions(store):
    v1 = store.create_version(ConfigType.RISK, "risk-v1", {})
    v2 = store.create_version(ConfigType.RISK, "risk-v2", {})
    v3 = store.create_version(ConfigType.EXECUTION, "exec-v1", {})
    versions = store.list_versions(ConfigType.RISK)
    assert len(versions) == 2


def test_duplicate_label_raises(store):
    store.create_version(ConfigType.RISK, "risk-v1", {})
    with pytest.raises(ValueError):
        store.create_version(ConfigType.RISK, "risk-v1", {})


def test_get_version_not_found(store):
    with pytest.raises(ConfigNotFoundError):
        store.get_version(uuid4())