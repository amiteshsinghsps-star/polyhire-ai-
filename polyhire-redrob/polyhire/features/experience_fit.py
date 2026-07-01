import jd_profile as jd


def experience_fit_score(years_of_experience: float) -> float:
    lo, hi = jd.EXPERIENCE_BAND
    if lo <= years_of_experience <= hi:
        return 1.0
    if (lo - 2) <= years_of_experience < lo or hi < years_of_experience <= (hi + 3):
        return 0.75
    return max(0.3, 1 - 0.08 * abs(years_of_experience - 7))
