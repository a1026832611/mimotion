from datetime import datetime

import pytz


BEIJING_TIMEZONE = pytz.timezone("Asia/Shanghai")


def get_beijing_time(now: datetime | None = None) -> datetime:
    """获取北京时间。"""
    if now is None:
        return datetime.now(BEIJING_TIMEZONE)
    if now.tzinfo is None:
        return BEIJING_TIMEZONE.localize(now)
    return now.astimezone(BEIJING_TIMEZONE)


def format_now(now: datetime | None = None) -> str:
    """格式化当前北京时间。"""
    return get_beijing_time(now).strftime("%Y-%m-%d %H:%M:%S")


def get_time_ms(now: datetime | None = None) -> str:
    """获取毫秒级时间戳字符串。"""
    current_time = get_beijing_time(now)
    return str(int(current_time.timestamp() * 1000))


def today_str(now: datetime | None = None) -> str:
    """获取北京时间对应的日期字符串。"""
    return get_beijing_time(now).strftime("%F")
