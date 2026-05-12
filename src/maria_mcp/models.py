from datetime import datetime

from pydantic import BaseModel


class DeviceInfo(BaseModel):
    data_center_id: int
    device_id: int
    device_name: str | None
    device_category_name: str | None
    device_type_name: str | None
    device_model_name: str | None
    manufacturer_name: str | None
    maintenance_provider_name: str | None
    location: str | None
    enable_monitor: int | None
    device_desc: str | None


class DeviceSummary(BaseModel):
    """장비 목록 조회용 경량 모델 (list_nearby_devices, list_devices_by_type, list_devices_by_ups)."""

    device_id: int
    device_name: str | None
    device_category_name: str | None
    device_type_name: str | None
    location: str | None
    enable_monitor: int | None


class DeviceSearchResult(DeviceSummary):
    """다중 조건 검색용 모델 (search_devices) — DeviceSummary + 전원/제조사 필드."""

    manufacturer_name: str | None
    connected_ups: str | None


class AlarmSummary(BaseModel):
    alarm_id: int | None
    alarm_name: str | None
    device_id: int | None
    device_name: str | None
    checkpoint_name: str | None
    severity: str | None
    confirm_state: str | None
    log_date: datetime | None
    closed_date: datetime | None = None
    message: str | None


class AlarmDetail(AlarmSummary):
    checkpoint_id: int | None
    acknowledged_date: datetime | None
    acknowledged_message: str | None
    closed_message: str | None


class AlarmSummaryStats(BaseModel):
    """활성 알람 심각도·상태 카운트 요약 (get_active_alarm_summary 전용)."""

    total_active: int
    by_severity: dict[str, int]
    unacknowledged: int
