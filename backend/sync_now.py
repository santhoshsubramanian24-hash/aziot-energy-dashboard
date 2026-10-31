import database
import tuya_service

s = database.get_settings()
client = tuya_service.TuyaClient(s['tuya_client_id'], s['tuya_client_secret'], s['tuya_region'])

print("Fetching daily energy records from Tuya Cloud...")
items = client.get_daily_energy_statistics(s['tuya_device_id'], '20261001', '20261102')
print(f"Fetched {len(items)} daily records!")

for item in items:
    database.upsert_daily_energy(item['date'], item['energy_kwh'], notes='Tuya Cloud Sync')
    print(f"  {item['date']}: {item['energy_kwh']} kWh")

records = database.get_energy_range('2026-10-01', '2026-11-02')
total = sum(r['energy_kwh'] for r in records)
print(f"\nSuccessfully stored in local database! Total: {total:.2f} kWh")

