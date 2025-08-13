import json
from zoo.logging_utils import SimpleLogger, get_logger


def test_level_filter_text(capsys):
    logger = SimpleLogger(level="INFO", log_format="text")
    logger.debug("debug should be suppressed")
    logger.info("info visible", step=1)
    out = capsys.readouterr().out.strip().splitlines()
    # Only one line (INFO) expected
    assert len(out) == 1
    assert "INFO:" in out[0]
    assert "step=1" in out[0]
    assert "debug" not in out[0]


def test_json_format_and_fields(capsys):
    logger = get_logger(level="DEBUG", log_format="json")
    logger.debug("dbg", k=123)
    logger.error("boom", code="E1")
    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line]
    assert len(lines) == 2
    rec0 = json.loads(lines[0])
    rec1 = json.loads(lines[1])
    # Basic required fields
    for rec in (rec0, rec1):
        assert set(["ts", "level", "msg"]).issubset(rec.keys())
        assert rec["ts"].endswith("Z")
    assert rec0["level"] == "DEBUG" and rec0["msg"] == "dbg" and rec0["k"] == 123
    assert rec1["level"] == "ERROR" and rec1["msg"] == "boom" and rec1["code"] == "E1"


def test_quiet_mode_equivalent_to_error_level(capsys):
    # Simulate quiet: effective level ERROR -> suppress INFO
    quiet_logger = get_logger(level="ERROR", log_format="text")
    quiet_logger.info("invisible")
    quiet_logger.error("visible")
    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line]
    assert len(lines) == 1
    assert "ERROR:" in lines[0]
    assert "visible" in lines[0]


def test_warn_and_error_pass_through(capsys):
    logger = SimpleLogger(level="WARN", log_format="text")
    logger.info("suppressed")
    logger.warn("warn msg")
    logger.error("err msg")
    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line]
    # Expect exactly WARN and ERROR
    assert len(lines) == 2
    assert any("WARN:" in line and "warn msg" in line for line in lines)
    assert any("ERROR:" in line and "err msg" in line for line in lines)
