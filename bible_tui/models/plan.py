from dataclasses import dataclass


@dataclass(frozen=True)
class PlanEntry:
    id: int
    plan_id: int
    day_number: int
    book_id: int
    book_name: str
    chapter_start: int
    chapter_end: int
    completed_at: str | None


@dataclass(frozen=True)
class ReadingPlan:
    id: int
    name: str
    plan_type: str
    start_date: str
    active: bool
