import requests
from typing import List, Dict, Optional

class MutualFundService:
    BASE_URL = "https://api.mfapi.in"

    def get_all_schemes(self) -> List[Dict]:
        response = requests.get(f"{self.BASE_URL}/mf")
        return response.json() if response.status_code == 200 else []

    def get_scheme_details(self, scheme_code: str) -> Optional[Dict]:
        response = requests.get(f"{self.BASE_URL}/mf/{scheme_code}")
        return response.json() if response.status_code == 200 else None

    def calculate_returns(self, nav_data: List[Dict], years: int) -> Optional[float]:
        if not nav_data or len(nav_data) < 2:
            return None
        days_required = years * 365
        if len(nav_data) < days_required:
            return None
        try:
            current_nav = float(nav_data[0]['nav'])
            past_nav = float(nav_data[min(days_required, len(nav_data)-1)]['nav'])
            returns = ((current_nav - past_nav) / past_nav) * 100
            return round(returns, 2)
        except:
            return None