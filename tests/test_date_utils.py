from datetime import date

import pytest

from tripcast.date_utils import get_recurring_dates, is_recurring_date, _nth_weekday_in_month


class TestNthWeekdayInMonth:
    def test_third_monday_april_2026(self):
        # 2026년 4월 셋째 월요일 = 4월 20일
        result = _nth_weekday_in_month(2026, 4, 0, 3)
        assert result == date(2026, 4, 20)

    def test_second_sunday_april_2026(self):
        # 2026년 4월 둘째 일요일 = 4월 12일
        result = _nth_weekday_in_month(2026, 4, 6, 2)
        assert result == date(2026, 4, 12)

    def test_last_weekday(self):
        # 2026년 4월 마지막 금요일 = 4월 24일
        result = _nth_weekday_in_month(2026, 4, 4, -1)
        assert result == date(2026, 4, 24)

    def test_fifth_weekday_nonexistent(self):
        # 2026년 4월 다섯째 월요일 없음
        result = _nth_weekday_in_month(2026, 4, 0, 5)
        assert result is None

    def test_invalid_n(self):
        with pytest.raises(ValueError):
            _nth_weekday_in_month(2026, 4, 0, 0)


class TestGetRecurringDates:
    REF = date(2026, 4, 27)  # 기준일 고정

    def test_third_monday(self):
        # 매월 셋째 월요일
        dates = get_recurring_dates([0], [3], months=1, reference=self.REF)
        assert all(d.weekday() == 0 for d in dates)
        # 4월 셋째 월요일(20일) 포함 확인
        assert date(2026, 4, 20) in dates

    def test_second_and_fourth_sunday(self):
        # 매월 둘째·넷째 일요일
        dates = get_recurring_dates([6], [2, 4], months=1, reference=self.REF)
        assert all(d.weekday() == 6 for d in dates)
        assert date(2026, 4, 12) in dates  # 둘째 일요일
        assert date(2026, 4, 26) in dates  # 넷째 일요일

    def test_sorted_output(self):
        dates = get_recurring_dates([0, 6], [1, 3], months=1, reference=self.REF)
        assert dates == sorted(dates)

    def test_invalid_weekday(self):
        with pytest.raises(ValueError):
            get_recurring_dates([7], [1])

    def test_invalid_week(self):
        with pytest.raises(ValueError):
            get_recurring_dates([0], [0])

    def test_range_respected(self):
        dates = get_recurring_dates([0], [1], months=1, reference=self.REF)
        ref = self.REF
        for d in dates:
            assert abs((d - ref).days) <= 31 * 1 + 31


class TestIsRecurringDate:
    def test_match_fourth_sunday(self):
        # 2026-04-26은 4월 넷째 일요일
        assert is_recurring_date([6], [4], reference=date(2026, 4, 26)) is True

    def test_match_third_monday(self):
        # 2026-04-20은 4월 셋째 월요일
        assert is_recurring_date([0], [3], reference=date(2026, 4, 20)) is True

    def test_no_match_wrong_week(self):
        # 2026-04-20은 셋째 월요일이지만, 둘째 월요일 패턴에는 해당 안 됨
        assert is_recurring_date([0], [2], reference=date(2026, 4, 20)) is False

    def test_no_match_wrong_weekday(self):
        # 2026-04-20은 월요일이지만, 화요일 패턴에는 해당 안 됨
        assert is_recurring_date([1], [3], reference=date(2026, 4, 20)) is False

    def test_match_multiple_weeks(self):
        # 둘째·넷째 일요일 패턴 — 4월 12일(둘째), 4월 26일(넷째) 모두 True
        assert is_recurring_date([6], [2, 4], reference=date(2026, 4, 12)) is True
        assert is_recurring_date([6], [2, 4], reference=date(2026, 4, 26)) is True
        assert is_recurring_date([6], [2, 4], reference=date(2026, 4, 19)) is False  # 셋째

    def test_match_last_week(self):
        # 2026-04-24는 4월 마지막 금요일
        assert is_recurring_date([4], [-1], reference=date(2026, 4, 24)) is True
        assert is_recurring_date([4], [-1], reference=date(2026, 4, 17)) is False

    def test_invalid_weekday(self):
        with pytest.raises(ValueError):
            is_recurring_date([7], [1], reference=date(2026, 4, 20))
