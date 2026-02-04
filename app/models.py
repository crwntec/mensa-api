from dataclasses import dataclass
from typing import Dict, List, TypedDict


class DayMeals(TypedDict):
    weekday: str
    meals: Dict[str, List[str]]


@dataclass
class Mealplan:
    year: int
    week: int
    days: Dict[str, DayMeals]
