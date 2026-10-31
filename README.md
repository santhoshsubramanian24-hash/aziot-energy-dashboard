# AZIOT Smart MCB — Custom Date-Range Energy & Bill Analyzer

A custom web application and dashboard built specifically for the **AZIOT Smart MCB (Tuya/Smart Life)** to overcome the Smart Life app's limitation of only showing fixed monthly/calendar periods.

---

## Key Features

1. **Custom Date-to-Date Range Picker**:
   - Select any arbitrary start and end date (e.g. `2026-10-15` to `2026-11-14`).
   - One-click presets: *This Bill Cycle*, *Last Bill Cycle*, *Last 7 Days*, *Last 30 Days*, *This Month*, *Last Month*.
2. **Accurate Consumption & Bill Calculation**:
   - Calculates exact total units (**kWh**) consumed in that date window.
   - Computes estimated electricity bill (**₹**) based on your custom tariff rate per unit.
   - Calculates daily average and detects your peak consumption day.
3. **Interactive Charts**:
   - Daily consumption bar chart.
   - Cumulative consumption trend line.
4. **Day-by-Day Detailed Log & Export**:
   - Full tabular breakdown with Day of Week, Units (kWh), and Cost.
   - Instant **CSV / Excel export**.
   - Manual reading backfill option for past electricity bills.
5. **Realtime MCB Telemetry**:
   - Live Voltage (V), Current (A), Active Power (W), and Relay status.
6. **Permanent Local Database**:
   - All records are saved in local SQLite (`energy_data.db`), meaning you retain your history indefinitely (even beyond Tuya Cloud's free retention period).

---

## Quick Start (Run in 1 Click)

Simply double-click **`run_dashboard.bat`** in this folder!

It will automatically:
1. Start the local server.
2. Open the dashboard in your web browser at: `http://localhost:5050`.

> **Tip:** You can also open the dashboard on your phone (connected to the same Wi-Fi) by browsing to `http://<YOUR_PC_IP>:5050`.

---

## Connecting to Your AZIOT MCB (Tuya Cloud Setup)

1. Go to the free **[Tuya IoT Platform](https://iot.tuya.com)** and create an account (or log in).
2. Go to **Cloud** ➔ **Development** ➔ **Create Cloud Project**.
3. Under **Device Connection**, choose **Smart Home** and select your data center (**India Data Center** for India).
4. After creating the project:
   - Go to the **Devices** tab ➔ **Link Tuya App Account**.
   - Open your **Smart Life** mobile app, tap **Profile / Me**, tap the **Scan [ - ]** icon at the top right, and scan the QR code on your PC screen.
   - Select "Read and Write" permission. Your AZIOT MCB will now show up under your project!
5. In your project **Overview**, copy:
   - **Access ID / Client ID**
   - **Access Secret / Client Secret**
6. Go to **Devices** ➔ copy your MCB's **Device ID**.
7. Open this dashboard (`http://localhost:5050`), click **Settings (⚙️)**, paste the 3 keys, and click **Test Connection**!

