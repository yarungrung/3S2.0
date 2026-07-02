"""Fare formulas preserved from the notebook."""

import math

def ubike_fare(minutes: float, identity: str) -> float:
    """Calculate YouBike fare from the notebook formula."""
    if identity == "senior":
        if minutes <= 30:
            return 0.0
        return math.ceil((minutes - 30) / 30) * 10.0
    if identity == "child":
        extra = math.ceil((minutes - 30) / 30) * 5.0 if minutes > 30 else 0.0
        return 5.0 + extra
    if minutes <= 30:
        return 5.0
    return 5.0 + (math.ceil((minutes - 30) / 30) * 10.0)


# =====================================================================
# 🚖 【使用者自訂區域：計程車費率公式】 (User-modifiable Taxi Fare Formula)
# 後續若有需要調整計程車起跳價、每段加成距離或夜間加成，請修改此處。
# =====================================================================
def taxi_fare(length_km: float, is_night_surge: bool = False) -> float:
    """
    Calculate taxi fare based on Taipei City statutory rates.
    - Base fare: 85 NTD for first 1.25 km.
    - Progressive fare: 5 NTD for every additional 200m (0.2 km).
    - Night surge: Add 20 NTD if active.
    """
    # 1. 計算基本里程與起跳價
    if length_km <= 1.25:
        fare = 85.0
    else:
        # 2. 超過基本里程，每200公尺加收5元 (無條件進位)
        extra_dist_m = (length_km - 1.25) * 1000.0
        fare = 85.0 + (math.ceil(extra_dist_m / 200.0) * 5.0)
    
    # 3. 夜間加成加收 20 元 (23:00 - 06:00)
    if is_night_surge:
        fare += 20.0
        
    return fare
# =====================================================================


# =====================================================================
# 🚌 【使用者自訂區域：公車費率公式】 (User-modifiable Bus Fare Formula)
# 後續若有需要調整公車分段收費或身分優惠金額，請修改此處。
# =====================================================================
def bus_fare(identity: str) -> float:
    """
    Calculate bus fare based on Taipei City bus fares.
    - Adult (成人): 15 NTD per segment.
    - Student (學生): 12 NTD per segment.
    - Child/Senior (兒童/敬老卡): 8 NTD per segment.
    """
    if identity == "adult":
        return 15.0
    elif identity == "student":
        return 12.0
    # 兒童與敬老身分
    return 8.0
# =====================================================================


def mrt_fare(length_km: float, identity: str) -> float:
    """Calculate MRT fare from the notebook formula."""
    if length_km <= 5.0:
        base_fare = 20.0
    else:
        base_fare = 20.0 + (math.ceil((length_km - 5.0) / 4.0) * 5.0)
    if identity in {"child", "senior"}:
        return float(math.ceil(base_fare * 0.5))
    return base_fare


def train_fare(length_km: float, identity: str) -> float:
    """Calculate TRA fare from the notebook formula."""
    base_fare = max(15.0, length_km * 1.46)
    if identity in {"child", "senior"}:
        return float(math.ceil(base_fare * 0.5))
    return float(math.ceil(base_fare))
