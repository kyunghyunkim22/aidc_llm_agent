"""Druid SQL 문자열 상수.

datasource: rollup_checkvalue_1min (1분 rollup)

`last_value` 는 Druid 복합 타입 `COMPLEX<serializablePairLongDouble>` 이라
SQL 에서 그대로 SELECT 하면 직렬화 페이로드가 반환된다. double 스칼라로
꺼내기 위해 GROUP BY __time 단위 집계 함수로 unwrap 한다.

unwrap 표현식 후보 (운영 Druid 접속 확보 후 diagnostics.py 로 검증해 확정):
  1) LATEST(last_value, 1024)          -- pair 의 value 만 추출
  2) ANY_VALUE(last_value)             -- 1분 슬롯 안에서 동일 값이라는 가정
  3) MAX(last_value)                   -- complex MAX (지원되는 Druid 버전 한정)

여기서는 (1) 을 기본으로 사용한다. 검증 후 다르면 본 상수만 교체한다.
"""

# 한 (data_center, device, checkpoint) 의 [range_start, range_end] 닫힌 구간
# 1분 rollup 시계열을 __time ASC 로 반환한다.
#
# parameters (Druid SQL parameterized): :dc, :dev, :cp, :range_start, :range_end
#   - :range_start / :range_end 는 ISO 8601 문자열 (예: 2026-06-25T10:00:00Z)
SELECT_CHECKPOINT_HISTORY = """
SELECT
    __time,
    LATEST(last_value, 1024) AS last_value,
    MAX(max_value)           AS max_value,
    MIN(min_value)           AS min_value,
    SUM(sum_value)           AS sum_value
FROM rollup_checkvalue_1min
WHERE data_center_id = ?
  AND device_id      = ?
  AND checkpoint_id  = ?
  AND __time >= TIME_PARSE(?)
  AND __time <= TIME_PARSE(?)
GROUP BY __time
ORDER BY __time ASC
""".strip()
