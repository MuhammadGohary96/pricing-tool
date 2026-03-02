from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class PricingDataServiceInterface(ABC):

    @abstractmethod
    def get_all_products(self, filters: dict = None) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_blended_pi_by_subcategory(self, filters: dict = None) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_coverage_funnel(self, filters: dict = None) -> dict:
        ...

    @abstractmethod
    def get_action_summary(self, filters: dict = None) -> dict:
        ...

    @abstractmethod
    def get_kpi_summary(self, filters: dict = None) -> dict:
        ...

    @abstractmethod
    def get_action_breakdown(self, filters: dict = None) -> list[dict]:
        ...

    @abstractmethod
    def get_worklist(
        self, filters: dict = None, page: int = 1, page_size: int = 50
    ) -> dict:
        ...

    @abstractmethod
    def get_match_reviews(
        self, filters: dict = None, page: int = 1, page_size: int = 20
    ) -> dict:
        ...

    @abstractmethod
    def get_staleness_heatmap(self, filters: dict = None) -> dict:
        ...

    @abstractmethod
    def get_executive_summary(self) -> dict:
        ...

    @abstractmethod
    def get_pi_trend(self) -> list[dict]:
        ...

    @abstractmethod
    def get_coverage_trend(self) -> list[dict]:
        ...

    @abstractmethod
    def get_category_performance(self, filters: dict = None) -> list[dict]:
        ...

    @abstractmethod
    def get_week_over_week(self) -> list[dict]:
        ...

    @abstractmethod
    def get_filter_options(self, main_category: Optional[str] = None) -> dict:
        ...
