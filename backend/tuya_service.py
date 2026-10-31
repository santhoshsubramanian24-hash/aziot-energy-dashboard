import logging
from typing import Dict, Any, Optional, List
from tuya_connector import TuyaOpenAPI

logger = logging.getLogger("tuya_service")

REGION_ENDPOINTS = {
    "in": "https://openapi.tuyain.com",  # India Data Center
    "us": "https://openapi.tuyaus.com",  # Western America
    "ue": "https://openapi.tuyaue.com",  # Eastern America
    "eu": "https://openapi.tuyaeu.com",  # Central Europe
    "we": "https://openapi.tuyawe.com",  # Western Europe
    "cn": "https://openapi.tuyacn.com"   # China Data Center
}

class TuyaClient:
    def __init__(self, client_id: str, client_secret: str, region: str = "in"):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.region = region.lower().strip()
        self.base_url = REGION_ENDPOINTS.get(self.region, REGION_ENDPOINTS["in"])
        self.api = TuyaOpenAPI(self.base_url, self.client_id, self.client_secret)
        self.connected = False

    def get_token(self) -> str:
        res = self.api.connect()
        if not res.get("success"):
            err_msg = res.get("msg", "Unknown error")
            code = res.get("code", "")
            raise Exception(f"Tuya Error ({code}): {err_msg}")
        self.connected = True
        return self.api.token_info.access_token

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Fetch current realtime status: voltage, current, power, cumulative kWh, switch state."""
        if not self.connected:
            self.get_token()

        res = self.api.get(f"/v1.0/devices/{device_id}/status")
        if not res.get("success"):
            raise Exception(f"Failed to fetch status: {res.get('msg')}")

        raw_status = res.get("result", [])
        parsed = {
            "voltage": 0.0,
            "current": 0.0,
            "power": 0.0,
            "cumulative_kwh": 0.0,
            "switch": False,
            "raw": raw_status
        }

        for item in raw_status:
            code = item.get("code", "")
            val = item.get("value")
            
            if code in ["switch", "switch_1", "switch_led"]:
                parsed["switch"] = bool(val)
            elif code in ["cur_voltage", "voltage", "va_voltage"]:
                try:
                    num = float(val)
                    parsed["voltage"] = round(num / 10.0 if num > 1000 else num, 1)
                except (ValueError, TypeError):
                    pass
            elif code in ["cur_current", "current", "ia_current"]:
                try:
                    num = float(val)
                    parsed["current"] = round(num / 1000.0, 3)
                except (ValueError, TypeError):
                    pass
            elif code in ["cur_power", "power", "pt_power"]:
                try:
                    num = float(val)
                    parsed["power"] = round(num / 10.0, 1)
                except (ValueError, TypeError):
                    pass
            elif code in ["add_ele", "total_forward_energy", "forward_energy_total", "energy"]:
                try:
                    num = float(val)
                    parsed["cumulative_kwh"] = round(num / 100.0 if num > 1000 else num, 2)
                except (ValueError, TypeError):
                    pass

        return parsed

    def get_daily_energy_statistics(self, device_id: str, start_day: str, end_day: str) -> List[Dict[str, Any]]:
        """
        Fetch historical daily energy statistics using device event logs.
        start_day & end_day: YYYYMMDD
        """
        if not self.connected:
            self.get_token()

        import datetime
        from collections import defaultdict

        try:
            # Parse start_day & end_day into timestamps
            s_dt = datetime.datetime.strptime(start_day, "%Y%m%d")
            e_dt = datetime.datetime.strptime(end_day, "%Y%m%d") + datetime.timedelta(days=1)
            start_ms = int(s_dt.timestamp() * 1000)
            end_ms = int(e_dt.timestamp() * 1000)
        except Exception:
            start_ms = int((datetime.datetime.now() - datetime.timedelta(days=30)).timestamp() * 1000)
            end_ms = int(datetime.datetime.now().timestamp() * 1000)

        daily_wh = defaultdict(float)
        row_key = None

        # Paginate through event logs (up to 20 pages = 2000 events)
        for _ in range(20):
            params = {
                "type": 7,
                "start_time": start_ms,
                "end_time": end_ms,
                "size": 100
            }
            if row_key:
                params["start_row_key"] = row_key

            res = self.api.get(f"/v1.0/devices/{device_id}/logs", params)
            if not res.get("success"):
                break

            result = res.get("result", {})
            logs = result.get("logs", [])
            for l in logs:
                if l.get("code") == "add_ele":
                    try:
                        val = float(l.get("value", 0))
                        t = datetime.datetime.fromtimestamp(l["event_time"] / 1000)
                        d_str = t.strftime("%Y-%m-%d")
                        daily_wh[d_str] += val
                    except (ValueError, TypeError):
                        pass

            if not result.get("has_next"):
                break
            row_key = result.get("next_row_key")

        items = []
        for d_str, raw_wh in sorted(daily_wh.items()):
            # Raw add_ele is Wh -> divide by 1000.0 to get kWh
            kwh = round(raw_wh / 1000.0, 3)
            items.append({"date": d_str, "energy_kwh": kwh})

        return items


