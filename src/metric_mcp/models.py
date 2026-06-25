from datetime import datetime

from pydantic import BaseModel


class CheckpointPoint(BaseModel):
    """1분 rollup 슬롯 1건."""

    time: datetime
    last_value: float | None
    max_value: float | None
    min_value: float | None
    sum_value: float | None


class CheckpointHistory(BaseModel):
    """한 (data_center, device, checkpoint) 의 최근 10분 시계열."""

    data_center_id: str
    device_id: str
    checkpoint_id: str
    range_start: datetime
    range_end: datetime
    points: list[CheckpointPoint]
