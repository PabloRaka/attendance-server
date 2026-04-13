import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def get_address_from_coords(lat: str, lon: str) -> Optional[str]:
    """
    Reverse geocode coordinates into a human-readable address (City, District, Village) 
    using OpenStreetMap Nominatim.
    """
    if not lat or not lon:
        return None

    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    headers = {
        "User-Agent": "IBIK-Attendance-System/1.0 (rakagusti@student.ibik.ac.id)", # Specific UA
        "Referer": "https://attendance.ibik.ac.id" # Contextual referrer
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                address = data.get("address", {})
                
                # Extracts the most specific location for Indonesia (Prioritize Kelurahan/Village)
                village = (
                    address.get("village") or 
                    address.get("hamlet") or 
                    address.get("neighbourhood") or
                    address.get("quarter") or
                    address.get("town")
                )
                
                subdistrict = address.get("subdistrict") or address.get("city_district") or address.get("district")
                suburb = address.get("suburb")

                # If village not found via specific keys, check suburb but avoid Kecamatan names
                if not village and suburb:
                    if not subdistrict or (suburb.lower() not in subdistrict.lower()):
                        village = suburb

                if village:
                    return f"Kel. {village}"
                
                # Fallback to Kecamatan if only that is available
                if subdistrict:
                    return f"Kec. {subdistrict}"
                
                return data.get("display_name", "").split(",")[0]
            else:
                logger.error(f"Nominatim API error: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Failed to reverse geocode: {e}")
        return None
