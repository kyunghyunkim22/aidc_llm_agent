"""화면(최종 답변만)과 파일(tool 호출/결과 포함) 분리 로깅 셋업."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_file_logger(log_dir: Path) -> tuple[logging.Logger, Path]:
    """파일 전용 로거 생성. 화면(stdout)으로는 흘리지 않는다.

    파일명에 사용자/PID 포함 — 여러 팀원이 동시에 ssh 접속해도 충돌 없음.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    user = os.environ.get("USER", "anon")
    pid = os.getpid()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{ts}_repl_{user}_{pid}.log"

    logger = logging.getLogger(f"test_harness.{pid}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    logger.addHandler(fh)

    return logger, log_path
