let energyChart = null;
let currentChartType = 'bar';
let cachedRecords = [];
let currentSettings = {
  billing_cycle_start_day: 1,
  flat_rate_per_unit: 7.5,
  currency_symbol: "₹"
};

// Initialize App
document.addEventListener("DOMContentLoaded", async () => {
  await loadSettings();
  setPreset('this-cycle');
  fetchLiveTelemetry();
  setInterval(fetchLiveTelemetry, 15000); // Polling every 15s
});

// Format Date YYYY-MM-DD
function formatDate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Load Settings from Backend
async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const data = await res.json();
      currentSettings = data;
      
      // Populate settings modal fields
      document.getElementById("settingRegion").value = data.tuya_region || "in";
      document.getElementById("settingClientId").value = data.tuya_client_id || "";
      document.getElementById("settingClientSecret").value = data.tuya_client_secret || "";
      document.getElementById("settingDeviceId").value = data.tuya_device_id || "";
      document.getElementById("settingCycleDay").value = data.billing_cycle_start_day || 1;
      document.getElementById("settingRate").value = data.flat_rate_per_unit || 7.5;
      
      document.getElementById("kpiCurrency").textContent = data.currency_symbol || "₹";
      document.getElementById("kpiRateLabel").textContent = `Rate: ${data.currency_symbol || '₹'}${data.flat_rate_per_unit || 7.50} / unit`;
    }
  } catch (err) {
    console.error("Error loading settings:", err);
  }
}

// Save Settings
async function saveSettings() {
  const payload = {
    tuya_region: document.getElementById("settingRegion").value,
    tuya_client_id: document.getElementById("settingClientId").value.trim(),
    tuya_client_secret: document.getElementById("settingClientSecret").value.trim(),
    tuya_device_id: document.getElementById("settingDeviceId").value.trim(),
    billing_cycle_start_day: parseInt(document.getElementById("settingCycleDay").value) || 1,
    flat_rate_per_unit: parseFloat(document.getElementById("settingRate").value) || 7.5
  };

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeSettingsModal();
      await loadSettings();
      fetchLiveTelemetry();
      loadEnergyData();
    } else {
      alert("Failed to save settings.");
    }
  } catch (err) {
    alert("Network error saving settings: " + err);
  }
}

// Test Connection
async function testConnection() {
  const statusEl = document.getElementById("testStatusMsg");
  const btn = document.getElementById("btnTestConn");
  btn.disabled = true;
  btn.textContent = "Testing...";
  statusEl.className = "test-status";
  statusEl.textContent = "Connecting to Tuya Cloud & AZIOT MCB...";
  statusEl.style.display = "block";

  try {
    // First save what's in the form fields
    await saveSettingsSilently();

    const res = await fetch("/api/test-connection", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      statusEl.className = "test-status success";
      const m = data.device_metrics || {};
      statusEl.innerHTML = `✅ <b>Connected Successfully!</b><br>Live Voltage: ${m.voltage}V | Power: ${m.power}W | Cumulative: ${m.cumulative_kwh} kWh`;
    } else {
      statusEl.className = "test-status error";
      statusEl.textContent = `❌ ${data.detail || "Connection failed. Check Client ID, Secret, & Device ID"}`;
    }
  } catch (err) {
    statusEl.className = "test-status error";
    statusEl.textContent = "❌ Connection test error: " + err;
  } finally {
    btn.disabled = false;
    btn.textContent = "🔌 Test Connection & Fetch Device Status";
  }
}

async function saveSettingsSilently() {
  const payload = {
    tuya_region: document.getElementById("settingRegion").value,
    tuya_client_id: document.getElementById("settingClientId").value.trim(),
    tuya_client_secret: document.getElementById("settingClientSecret").value.trim(),
    tuya_device_id: document.getElementById("settingDeviceId").value.trim(),
    billing_cycle_start_day: parseInt(document.getElementById("settingCycleDay").value) || 1,
    flat_rate_per_unit: parseFloat(document.getElementById("settingRate").value) || 7.5
  };
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

// Fetch Live Telemetry
async function fetchLiveTelemetry() {
  try {
    const res = await fetch("/api/live-status");
    if (!res.ok) return;
    const data = await res.json();
    const dot = document.getElementById("liveDot");
    const statusText = document.getElementById("liveStatusText");

    if (data.configured && data.online) {
      dot.className = "dot online";
      statusText.textContent = "MCB Online";
      const m = data.metrics || {};
      document.getElementById("liveVoltage").textContent = `${m.voltage || '--'} V`;
      document.getElementById("liveCurrent").textContent = `${m.current || '--'} A`;
      document.getElementById("livePower").textContent = `${m.power || '--'} W`;
      document.getElementById("liveCumulative").textContent = `${m.cumulative_kwh || '--'} kWh`;
    } else if (data.configured && !data.online) {
      dot.className = "dot offline";
      statusText.textContent = "MCB Offline / Error";
    } else {
      dot.className = "dot";
      statusText.textContent = "Setup Required";
    }
  } catch (err) {
    console.warn("Failed to fetch live telemetry:", err);
  }
}

// Quick Preset Handlers
function setPreset(preset) {
  document.querySelectorAll(".pill-btn").forEach(b => b.classList.remove("active"));
  if (event && event.target && event.target.classList.contains("pill-btn")) {
    event.target.classList.add("active");
  }

  const today = new Date();
  let start = new Date();
  let end = new Date();

  const cycleDay = currentSettings.billing_cycle_start_day || 1;

  if (preset === 'this-cycle') {
    if (today.getDate() >= cycleDay) {
      start = new Date(today.getFullYear(), today.getMonth(), cycleDay);
    } else {
      // Started last month
      start = new Date(today.getFullYear(), today.getMonth() - 1, cycleDay);
    }
    end = today;
  } else if (preset === 'last-cycle') {
    if (today.getDate() >= cycleDay) {
      start = new Date(today.getFullYear(), today.getMonth() - 1, cycleDay);
      end = new Date(today.getFullYear(), today.getMonth(), cycleDay - 1);
    } else {
      start = new Date(today.getFullYear(), today.getMonth() - 2, cycleDay);
      end = new Date(today.getFullYear(), today.getMonth() - 1, cycleDay - 1);
    }
  } else if (preset === 'last-7') {
    start = new Date();
    start.setDate(today.getDate() - 6);
    end = today;
  } else if (preset === 'last-30') {
    start = new Date();
    start.setDate(today.getDate() - 29);
    end = today;
  } else if (preset === 'this-month') {
    start = new Date(today.getFullYear(), today.getMonth(), 1);
    end = today;
  } else if (preset === 'last-month') {
    start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    end = new Date(today.getFullYear(), today.getMonth(), 0);
  }

  document.getElementById("startDate").value = formatDate(start);
  document.getElementById("endDate").value = formatDate(end);
  loadEnergyData();
}

// Load Energy Data
async function loadEnergyData() {
  const start = document.getElementById("startDate").value;
  const end = document.getElementById("endDate").value;
  if (!start || !end) return;

  try {
    const res = await fetch(`/api/energy?start_date=${start}&end_date=${end}`);
    if (!res.ok) {
      console.error("Failed to fetch energy data");
      return;
    }
    const data = await res.json();
    cachedRecords = data.records || [];

    // Update KPI Cards
    document.getElementById("kpiTotalUnits").textContent = data.total_kwh.toFixed(2);
    document.getElementById("kpiDaysLabel").textContent = `For ${data.days_count} recorded days`;
    document.getElementById("kpiTotalCost").textContent = data.total_cost.toFixed(2);
    document.getElementById("kpiAvgUnits").textContent = data.avg_daily_kwh.toFixed(2);
    
    const dailyCost = (data.avg_daily_kwh * data.rate_per_unit).toFixed(2);
    document.getElementById("kpiAvgCost").textContent = `~${data.currency}${dailyCost} / day`;

    document.getElementById("kpiPeakUnits").textContent = data.peak_day.kwh.toFixed(2);
    document.getElementById("kpiPeakDate").textContent = data.peak_day.date !== "-" ? `on ${data.peak_day.date}` : "No peak recorded";

    // Update Visual Chart
    renderChart(cachedRecords);

    // Update Table
    renderTable(cachedRecords, data.currency);

  } catch (err) {
    console.error("Error loading energy data:", err);
  }
}

// Render Chart.js
function renderChart(records) {
  const ctx = document.getElementById("energyChart").getContext("2d");
  const labels = records.map(r => r.date);
  const dailyUnits = records.map(r => r.energy_kwh);

  // Compute cumulative values for line chart
  let cum = 0;
  const cumulativeUnits = records.map(r => {
    cum += r.energy_kwh;
    return parseFloat(cum.toFixed(2));
  });

  if (energyChart) {
    energyChart.destroy();
  }

  if (currentChartType === 'bar') {
    energyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Daily Units (kWh)',
          data: dailyUnits,
          backgroundColor: 'rgba(6, 182, 212, 0.65)',
          borderColor: '#06B6D4',
          borderWidth: 1.5,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => ` ${context.parsed.y.toFixed(2)} kWh (~₹${(context.parsed.y * (currentSettings.flat_rate_per_unit || 7.5)).toFixed(2)})`
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(35, 51, 84, 0.4)' },
            ticks: { color: '#94A3B8', font: { family: 'JetBrains Mono', size: 11 } }
          },
          y: {
            grid: { color: 'rgba(35, 51, 84, 0.4)' },
            ticks: { color: '#94A3B8', font: { family: 'JetBrains Mono', size: 11 } }
          }
        }
      }
    });
  } else {
    // Cumulative Line
    energyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Cumulative kWh',
          data: cumulativeUnits,
          borderColor: '#10B981',
          backgroundColor: 'rgba(16, 185, 129, 0.15)',
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointBackgroundColor: '#10B981'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { color: 'rgba(35, 51, 84, 0.4)' },
            ticks: { color: '#94A3B8', font: { family: 'JetBrains Mono', size: 11 } }
          },
          y: {
            grid: { color: 'rgba(35, 51, 84, 0.4)' },
            ticks: { color: '#94A3B8', font: { family: 'JetBrains Mono', size: 11 } }
          }
        }
      }
    });
  }
}

function setChartType(type) {
  currentChartType = type;
  document.getElementById("btnBarChart").classList.toggle("active", type === 'bar');
  document.getElementById("btnLineChart").classList.toggle("active", type === 'line');
  renderChart(cachedRecords);
}

// Render Table
function renderTable(records, currency) {
  const tbody = document.getElementById("tableBody");
  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No records for this date range. Click "Sync Cloud" to fetch recent data.</td></tr>`;
    return;
  }

  const daysOfWeek = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  let html = "";
  // Display newest date first in table
  const reversed = [...records].reverse();

  reversed.forEach(r => {
    const d = new Date(r.date + "T00:00:00");
    const dayName = daysOfWeek[d.getDay()] || "";
    const cum = r.cumulative_kwh > 0 ? `${r.cumulative_kwh.toFixed(2)}` : '--';
    html += `
      <tr>
        <td><b>${r.date}</b></td>
        <td style="color: #94A3B8;">${dayName}</td>
        <td style="color: #06B6D4; font-weight: 600;">${r.energy_kwh.toFixed(2)}</td>
        <td style="color: #10B981; font-weight: 600;">${currency}${r.cost.toFixed(2)}</td>
        <td style="color: #94A3B8;">${cum}</td>
        <td style="font-size: 11px; color: #64748B;">${r.notes || 'API Sync'}</td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

// Trigger Cloud Sync
async function triggerSync() {
  const btn = document.getElementById("btnSync");
  btn.disabled = true;
  btn.innerHTML = `<span class="icon">⏳</span> Syncing...`;

  try {
    const res = await fetch("/api/sync?days=30", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      alert(`Sync Complete! Updated ${data.synced_days} day(s) from Tuya Cloud.`);
      fetchLiveTelemetry();
      loadEnergyData();
    } else {
      alert(`Sync failed: ${data.detail || 'Check API credentials in Settings'}`);
    }
  } catch (err) {
    alert("Sync error: " + err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="icon">🔄</span> Sync Cloud`;
  }
}

// Export CSV
function exportCSV() {
  if (!cachedRecords || cachedRecords.length === 0) {
    alert("No records to export.");
    return;
  }

  let csv = "Date,Day,Units Consumed (kWh),Estimated Cost (INR),Meter Cumulative (kWh),Notes\n";
  const daysOfWeek = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  cachedRecords.forEach(r => {
    const d = new Date(r.date + "T00:00:00");
    const dayName = daysOfWeek[d.getDay()] || "";
    csv += `"${r.date}","${dayName}",${r.energy_kwh},${r.cost},${r.cumulative_kwh || ''},"${r.notes || ''}"\n`;
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const s = document.getElementById("startDate").value;
  const e = document.getElementById("endDate").value;
  a.href = url;
  a.download = `AZIOT_MCB_Energy_${s}_to_${e}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// Modals
function openSettingsModal() {
  document.getElementById("settingsModal").classList.add("active");
}
function closeSettingsModal() {
  document.getElementById("settingsModal").classList.remove("active");
}
function openManualModal() {
  document.getElementById("manualDate").value = formatDate(new Date());
  document.getElementById("manualModal").classList.add("active");
}
function closeManualModal() {
  document.getElementById("manualModal").classList.remove("active");
}

async function saveManualEntry() {
  const d = document.getElementById("manualDate").value;
  const u = parseFloat(document.getElementById("manualUnits").value);
  const c = parseFloat(document.getElementById("manualCumulative").value) || 0;
  const n = document.getElementById("manualNotes").value;

  if (!d || isNaN(u)) {
    alert("Please enter a valid date and units.");
    return;
  }

  try {
    const res = await fetch("/api/manual-entry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: d, energy_kwh: u, cumulative_kwh: c, notes: n })
    });
    if (res.ok) {
      closeManualModal();
      loadEnergyData();
    }
  } catch (err) {
    alert("Error saving manual entry: " + err);
  }
}

