# config.py
import os

API_KEY = os.getenv("API_KEY")
API_HEADER = "x-api-key"
EXPECTED_KEY = API_KEY

INSTALLATION_CREDENTIALS = {
    "75752": ("wsepirus2026", "Wsepirus@@2026"),
    "77073": ("ophthalmic@", "@ophthalmica10"),
    "30000": ("clinicB", "ClinicB@@2026"),
    "40000": ("centerC", "CenterC@@2026"),
    "50000": ("unitD", "UnitD@@2026")
}
