"""Obtém a hora atual em uma cidade."""

from datetime import datetime

import pytz
from langchain.tools import tool

CITY_TIMEZONES = {
    "new york": "America/New_York",
    "london": "Europe/London",
    "tokyo": "Asia/Tokyo",
    "sydney": "Australia/Sydney",
    "sao paulo": "America/Sao_Paulo",
    "rio de janeiro": "America/Sao_Paulo",
    "brasilia": "America/Sao_Paulo",
    "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "dalllas": "America/Chicago",
    "miami": "America/New_York",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "madrid": "Europe/Madrid",
    "moscow": "Europe/Moscow",
    "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "seoul": "Asia/Seoul",
    "mumbai": "Asia/Kolkata",
    "dubai": "Asia/Dubai",
    "cape town": "Africa/Johannesburg",
    "nairobi": "Africa/Nairobi",
    "toronto": "America/Toronto",
    "mexico city": "America/Mexico_City",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "lima": "America/Lima",
    "bogota": "America/Bogota",
}


@tool
def get_time(city: str) -> str:
    """Retorna a hora atual em uma cidade.

    Cidades suportadas: New York, London, Tokyo, Sydney, São Paulo,
    Rio de Janeiro, Brasilia, Los Angeles, Chicago, Miami, Paris,
    Berlin, Madrid, Moscow, Beijing, Shanghai, Seoul, Mumbai, Dubai,
    Cape Town, Nairobi, Toronto, Mexico City, Buenos Aires, Lima, Bogota.
    """
    city_key = city.lower().strip()
    tz_key = CITY_TIMEZONES.get(city_key)
    if not tz_key:
        available = ", ".join(sorted(CITY_TIMEZONES.keys()))
        return f"City not found. Available cities: {available}"

    try:
        tz = pytz.timezone(tz_key)
        current_time = datetime.now(tz).strftime("%I:%M %p")
        return f"The current time in {city.title()} is {current_time} ({tz_key})."
    except Exception as e:
        return f"Error: {e}"
