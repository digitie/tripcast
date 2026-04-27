# tripcast

여행 앱에서 공통으로 사용하는 Python 유틸리티 라이브러리.

## 프로젝트 개요

- **언어**: Python 3.11+
- **목적**: 여행 앱 전반에서 재사용 가능한 유틸리티 함수 모음
- **원칙**: 엄격한 타입 힌트, 완전한 docstring, 단위 테스트 필수

## 코딩 표준

### 타입 힌트
- 모든 함수에 파라미터와 반환 타입 명시 (Python 3.11+ 문법)
- `from __future__ import annotations` 불필요 (3.11+이므로 native 사용)
- `Any` 사용 금지 — 정확한 타입으로 대체
- `TypeAlias`, `TypeVar`, `Protocol` 적극 활용

### Docstring
- Google Style 사용
- Args, Returns, Raises 섹션 필수
- 예제는 doctest 형식으로 작성

### 예시
```python
def get_recurring_dates(
    weekdays: list[int],
    weeks: list[int],
    months: int = 1,
) -> list[date]:
    """월별 N번째 요일 패턴에 해당하는 날짜를 반환한다.

    Args:
        weekdays: 요일 목록. 0=월요일 ... 6=일요일.
        weeks: 주차 목록. 1~5 또는 -1(마지막 주).
        months: 오늘 기준 앞뒤로 탐색할 개월 수.

    Returns:
        패턴에 해당하는 날짜 목록 (오름차순 정렬).

    Raises:
        ValueError: weekdays 또는 weeks 값이 범위를 벗어난 경우.

    Examples:
        >>> from datetime import date
        >>> dates = get_recurring_dates(weekdays=[0], weeks=[3])  # 매월 셋째 월요일
    """
```

## 프로젝트 구조

```
tripcast/
├── CLAUDE.md
├── pyproject.toml
├── tripcast/
│   ├── __init__.py
│   └── date_utils.py      # 날짜 패턴 유틸리티
└── tests/
    ├── __init__.py
    └── test_date_utils.py
```

## 모듈 목록

| 모듈 | 설명 |
|------|------|
| `date_utils` | 반복 일정 패턴(N번째 요일 등) → 날짜 변환 |

## 개발 명령어

```bash
# 의존성 설치
pip install -e ".[dev]"

# 테스트 실행
pytest tests/ -v

# 타입 검사
mypy tripcast/

# 린트
ruff check tripcast/
```

## Agents / Skills

이 저장소는 Claude Code + GitHub MCP를 통해 관리된다.

### 사용 중인 Skills
- **init**: 새 CLAUDE.md 초기화
- **review**: PR 코드 리뷰
- **security-review**: 보안 취약점 점검
- **simplify**: 변경 코드 품질/효율성 검토 후 개선

### 개발 브랜치 규칙
- 작업 브랜치: `claude/<feature>-<id>` 형식
- `main`으로 직접 push 금지
- PR을 통해 merge

## 외부 의존성

| 패키지 | 용도 |
|--------|------|
| `python-dateutil` | 복잡한 날짜 반복 규칙 처리 (rrule) |

> 외부 REST API 연동이 필요한 경우 각 모듈 docstring에 엔드포인트와 인증 방식을 명시한다.
