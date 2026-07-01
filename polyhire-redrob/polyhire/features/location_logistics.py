import jd_profile as jd


def location_logistics_score(profile: dict, signals: dict) -> float:
    location = (profile.get("location") or "").lower()
    country = (profile.get("country") or "").lower()

    if country and country != "india":
        loc_score = 0.25
    elif any(c in location for c in jd.PREFERRED_LOCATIONS_TIER1):
        loc_score = 1.0
    elif any(c in location for c in jd.ACCEPTABLE_LOCATIONS):
        loc_score = 0.85
    elif signals.get("willing_to_relocate"):
        loc_score = 0.7
    else:
        loc_score = 0.45

    notice = signals.get("notice_period_days", 60) or 0
    if notice <= 30:
        notice_mult = 1.0
    elif notice <= 60:
        notice_mult = 0.92
    elif notice <= 90:
        notice_mult = 0.80
    else:
        notice_mult = 0.65

    return loc_score * notice_mult
