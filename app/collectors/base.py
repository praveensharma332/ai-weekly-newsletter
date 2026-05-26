from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseCollector(ABC):
    """Abstract Base Class for all article/news collectors."""

    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """Collects articles and returns a list of dictionaries containing:
        - title: str
        - source: str
        - url: str
        - publish_date: datetime
        - raw_content: str
        """
        pass
