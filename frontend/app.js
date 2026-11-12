let charts = {};
let initializedDates = false;
const $ = (id) => document.getElementById(id);
const money = (value) => value == null ? "Not available" : `₹${Number(value).toLocaleString("en-IN", {maximumFractionDigits: 2})}`;
const chart = (id, labels, values, colors) => {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), {type: "doughnut", data: {labels, datasets: [{data: values, backgroundColor: colors, borderWidth: 0}]}, options: {plugins: {legend: {position: "bottom", labels: {usePointStyle: true, padding: 18}}}, cutout: "64%"}});
};
async function loadDashboard() {
  const params = new URLSearchParams();
  if (initializedDates && $("start").value && $("end").value) { params.set("start", $("start").value); params.set("end", $("end").value); }
  const data = await fetch(`/api/dashboard?${params}`).then(r => r.json());
  if (!initializedDates && data.date_start && data.date_end) {
    $("start").value = data.date_start;
    $("end").value = data.date_end;
    initializedDates = true;
  }
  $("catalog-value").textContent = money(data.catalog_value); $("customers").textContent = data.customers ?? "—";
  $("packs").textContent = data.packs ?? "—";
  $("rows").textContent = Number(data.rows).toLocaleString(); $("coverage").textContent = `${data.date_start || "—"} to ${data.date_end || "—"}`;
  $("notice").textContent = data.rows === 0
    ? "No rows match the selected date range. Choose dates between 2022-01-01 and 2024-12-31."
    : `Synthetic sample data: ${data.source}. The dataset contains dimensions and prices, but revenue, units, order, inventory, and production measures are not populated.`;
  chart("segments", data.segments.map(x => x.segment), data.segments.map(x => x.rows), ["#164b36","#4f9270","#9bc28c","#d8f36a"]);
  chart("channels", data.channels.map(x => x.channel), data.channels.map(x => x.rows), ["#164b36","#f2a65a","#8db8a2","#d8f36a"]);
  chart("products", data.products.map(x => x.product), data.products.map(x => x.rows), ["#164b36","#d8f36a","#f2a65a"]);
}
function makeTable(id, rows) {
  const table = $(id); table.innerHTML = "";
  if (!rows.length) { table.innerHTML = "<tr><td class='empty'>No data available.</td></tr>"; return; }
  const columns = Object.keys(rows[0]); table.innerHTML = `<thead><tr>${columns.map(x => `<th>${x.replaceAll("_"," ")}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(x => `<td>${row[x] ?? "—"}</td>`).join("")}</tr>`).join("")}</tbody>`;
}
async function loadSales() { const data = await fetch("/api/sales").then(r => r.json()); makeTable("sales-table", data.rows); }
async function loadQuality() { const data = await fetch("/api/quality").then(r => r.json()); $("quality-count").textContent = `${data.sales.length} columns`; makeTable("quality-table", data.sales); }
document.querySelectorAll(".nav-link").forEach(button => button.addEventListener("click", async () => { document.querySelectorAll(".nav-link").forEach(x => x.classList.remove("active")); button.classList.add("active"); document.querySelectorAll(".page-section").forEach(x => x.classList.add("hidden")); $(button.dataset.section).classList.remove("hidden"); if (button.dataset.section === "sales") await loadSales(); if (button.dataset.section === "quality") await loadQuality(); }));
$("apply").addEventListener("click", loadDashboard);
loadDashboard().catch(error => { $("notice").textContent = `Could not load dashboard data: ${error.message}`; });
