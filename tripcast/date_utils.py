"""날짜 패턴 유틸리티.

월별 N번째 요일 패턴("매월 셋째 월요일" 등)을 실제 날짜 목록으로 변환한다.
외부 라이브러리 없이 표준 라이브러리만 사용한다.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


# 0=월요일 ... 6=일요일 (Python weekday() 기준)
Weekday = int   # 0–6
WeekOrdinal = int  # 1–5, -1(마지막 주)


def _nth_weekday_in_month(year: int, month: int, weekday: Weekday, n: WeekOrdinal) -> date | None:
    """특정 연월에서 N번째 weekday 날짜를 반환한다.

    Args:
        year: 연도.
        month: 월 (1–12).
        weekday: 요일 (0=월 … 6=일).
        n: 주차. 1–5는 해당 주차, -1은 마지막 주차.

    Returns:
        해당 날짜. 해당 주차가 그 달에 존재하지 않으면 None.

    Raises:
        ValueError: n이 -1, 1–5 범위를 벗어난 경우.
    """
    if n not in (-1, 1, 2, 3, 4, 5):
        raise ValueError(f"weeks 값은 1–5 또는 -1이어야 합니다. 입력값: {n}")

    _, days_in_month = calendar.monthrange(year, month)

    if n == -1:
        # 월말부터 역순으로 탐색
        for day in range(days_in_month, 0, -1):
            if date(year, month, day).weekday() == weekday:
                return date(year, month, day)
        return None  # unreachable

    count = 0
    for day in range(1, days_in_month + 1):
        if date(year, month, day).weekday() == weekday:
            count += 1
            if count == n:
                return date(year, month, day)
    return None


def _iter_months(start: date, end: date):
    """start부터 end까지 (year, month) 쌍을 순서대로 생성한다."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1


def get_recurring_dates(
    weekdays: list[Weekday],
    weeks: list[WeekOrdinal],
    months: int = 1,
    *,
    reference: date | None = None,
) -> list[date]:
    """월별 N번째 요일 패턴에 해당하는 날짜를 반환한다.

    오늘(또는 reference)을 기준으로 앞뒤 months개월 범위 안의 날짜를 반환한다.

    Args:
        weekdays: 요일 목록. 0=월요일 … 6=일요일.
                  예) [0] → 월요일, [6] → 일요일
        weeks: 주차 목록. 1–5(해당 주차) 또는 -1(마지막 주차).
               예) [3] → 셋째 주, [2, 4] → 둘째·넷째 주
        months: 기준일 앞뒤로 탐색할 개월 수. 기본값 1.
        reference: 기준 날짜. None이면 오늘(date.today()).

    Returns:
        패턴에 해당하는 날짜 목록 (오름차순 정렬).

    Raises:
        ValueError: weekdays 값이 0–6 범위를 벗어난 경우.
        ValueError: weeks 값이 -1, 1–5 범위를 벗어난 경우.

    Examples:
        매월 셋째 월요일:
        >>> dates = get_recurring_dates(weekdays=[0], weeks=[3])

        매월 둘째·넷째 일요일:
        >>> dates = get_recurring_dates(weekdays=[6], weeks=[2, 4])

        매월 첫째·셋째 토요일, 범위 2개월:
        >>> dates = get_recurring_dates(weekdays=[5], weeks=[1, 3], months=2)
    """
    for wd in weekdays:
        if not (0 <= wd <= 6):
            raise ValueError(f"weekdays 값은 0–6이어야 합니다. 입력값: {wd}")

    today = reference or date.today()

    # 기준일 ±months 개월 범위 계산
    def shift_month(d: date, delta: int) -> date:
        month = d.month + delta
        year = d.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(d.day, last_day))

    range_start = shift_month(today, -months)
    range_end = shift_month(today, months)

    results: list[date] = []
    for year, month in _iter_months(range_start, range_end):
        for weekday in weekdays:
            for week in weeks:
                d = _nth_weekday_in_month(year, month, weekday, week)
                if d is not None and range_start <= d <= range_end:
                    results.append(d)

    results.sort()
    return results
