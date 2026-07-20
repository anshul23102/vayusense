import pytest

from agents.aqi import ARCHIVE_UNITS, category, overall_aqi, pollutant_aqi, to_epa_unit


# Published EPA anchor points (2024 PM2.5 table)
@pytest.mark.parametrize("param,value,unit,expected", [
    ("pm25", 9.0, "ugm3", 50),
    ("pm25", 35.4, "ugm3", 100),
    ("pm25", 55.4, "ugm3", 150),
    ("pm25", 125.4, "ugm3", 200),
    ("pm25", 225.4, "ugm3", 300),
    ("pm10", 54, "ugm3", 50),
    ("pm10", 154, "ugm3", 100),
    ("co", 4.4, "ppm", 50),
    ("co", 9.4, "ppm", 100),
    ("so2", 35, "ppb", 50),
    ("no2", 53, "ppb", 50),
    ("o3", 70, "ppb", 100),
])
def test_epa_anchor_points(param, value, unit, expected):
    assert pollutant_aqi(param, value, unit) == expected


def test_clamps_at_500_above_table():
    assert pollutant_aqi("pm25", 999.0, "ugm3") == 500


def test_unknown_or_negative_returns_none():
    assert pollutant_aqi("xyz", 10, "ugm3") is None
    assert pollutant_aqi("pm25", -1, "ugm3") is None


def test_unit_conversion_no2_ugm3():
    # 100 ug/m3 NO2 -> 53.15 ppb -> truncated 53 ppb -> AQI 50 (top of Good)
    assert pollutant_aqi("no2", 100.0, "ugm3") == 50


def test_unit_conversion_co_mgm3():
    # 5.0 mg/m3 CO -> ~4.36 ppm -> AQI in Good band (<=50)
    v = to_epa_unit("co", 5.0, "mgm3")
    assert 4.3 < v < 4.45
    assert pollutant_aqi("co", 5.0, "mgm3") <= 50


def test_overall_picks_dominant():
    aqi, dominant, subs = overall_aqi(
        {"pm25": 55.4, "no2": 20.0}, {"pm25": "ugm3", "no2": "ugm3"}
    )
    assert aqi == 150 and dominant == "pm25"
    assert subs["pm25"] == 150 and subs["no2"] < 50


def test_category_bands():
    assert category(50)["key"] == "good"
    assert category(51)["key"] == "moderate"
    assert category(150)["label"] == "Poor"
    assert category(300)["key"] == "severe"
    assert category(301)["key"] == "hazardous"
    assert category(301)["color"] == "#b04a63"


def test_archive_units_cover_all_params():
    assert set(ARCHIVE_UNITS) == {"pm25", "pm10", "no2", "o3", "so2", "co"}
    assert ARCHIVE_UNITS["co"] == "mgm3"
