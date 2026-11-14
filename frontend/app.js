let charts = {};
let initializedDates = false;
let currentUser = null;
const $ = (id) => document.getElementById(id);
const money = (value) => value == null ? "Not available" : `₹${Number(value).toLocaleString("en-IN", {maximumFractionDigits: 2})}`;
const chart = (id, labels, values, colors, type = "doughnut", options = {}) => {
  if (charts[id]) charts[id].destroy();
  const canvas = $(id);
  if (!canvas || !labels.length) return;
  charts[id] = new Chart(canvas, {type, data: {labels, datasets: [{label: type === "bar" ? "Activity records" : undefined, data: values, backgroundColor: colors, borderWidth: 0}]}, options: {plugins: {legend: {position: "bottom", labels: {usePointStyle: true, padding: 18}}}, ...options}});
};
const lineChart = (id, labels, actual, predicted) => {
  if (charts[id]) charts[id].destroy();
  const canvas = $(id);
  if (!canvas || !labels.length) return;
  const datasets = [{label: "Actual", data: actual, borderColor: "#164b36", backgroundColor: "#164b36", tension: 0.3, spanGaps: false}];
  if (predicted.length) datasets.push({label: "Projected", data: predicted, borderColor: "#f2a65a", backgroundColor: "#f2a65a", borderDash: [6, 4], tension: 0.3, spanGaps: false});
  charts[id] = new Chart(canvas, {
    type: "line",
    data: {labels, datasets},
    options: {scales: {y: {beginAtZero: true}}, plugins: {legend: {position: "bottom"}}},
  });
};
async function loadDashboard() {
  const params = new URLSearchParams();
  if (initializedDates && $("start").value && $("end").value) { params.set("start", $("start").value); params.set("end", $("end").value); }
  const response = await fetch(`/api/dashboard?${params}`);
  if (!response.ok) throw new Error(`Dashboard request failed (HTTP ${response.status})`);
  const data = await response.json();
  const rows = key => Array.isArray(data[key]) ? data[key] : [];
  const productPerformance = rows("product_performance");
  const monthlyTrend = rows("monthly_trend");
  const regions = rows("regions");
  const customerTypes = rows("customer_types");
  const packTypes = rows("pack_types");
  const actualMonthlyValues = monthlyTrend.map(x => Number(x.actual)).filter(Number.isFinite);
  if (!initializedDates && data.date_start && data.date_end) {
    $("start").value = data.date_start;
    $("end").value = data.date_end;
    initializedDates = true;
  }
  $("catalog-value").textContent = money(data.catalog_value); $("customers").textContent = data.customers ?? "—";
  $("packs").textContent = data.packs ?? "—";
  $("rows").textContent = Number(data.rows).toLocaleString(); $("coverage").textContent = `${data.date_start || "—"} to ${data.date_end || "—"}`;
  $("regions-count").textContent = regions.length || "—";
  $("top-region").textContent = regions[0]?.dimension || "—";
  $("top-customer-type").textContent = customerTypes[0]?.dimension || "—";
  $("monthly-average").textContent = actualMonthlyValues.length
    ? Math.round(actualMonthlyValues.reduce((total, value) => total + value, 0) / actualMonthlyValues.length).toLocaleString()
    : "—";
  $("orders-made").textContent = data.metrics.orders_made ?? "Not available";
  $("orders-received").textContent = data.metrics.orders_received ?? "Not available";
  $("payment-pending").textContent = money(data.metrics.payment_pending);
  $("user-orders-made").textContent = data.metrics.orders_made ?? "Not available";
  $("user-orders-received").textContent = data.metrics.orders_received ?? "Not available";
  $("user-orders-pending").textContent = data.metrics.orders_pending ?? "Not available";
  $("user-amount-paid").textContent = money(data.metrics.amount_paid);
  $("user-payment-pending").textContent = money(data.metrics.payment_pending);
  $("user-dashboard-title").textContent = `${currentUser.username} account`;
  $("user-data-scope").textContent = `${currentUser.department} · ${currentUser.customer_id}`;
  $("admin-revenue").textContent = money(data.metrics.revenue);
  $("admin-billed").textContent = money(data.metrics.amount_billed);
  $("admin-paid").textContent = money(data.metrics.amount_paid);
  $("admin-pending").textContent = money(data.metrics.payment_pending);
  $("admin-profit").textContent = money(data.metrics.profit);
  $("admin-growth").textContent = data.metrics.sales_growth_pct == null ? "Not available" : `${data.metrics.sales_growth_pct >= 0 ? "+" : ""}${data.metrics.sales_growth_pct}%`;
  $("admin-aov").textContent = money(data.metrics.average_order_value);
  $("admin-units").textContent = data.metrics.units == null ? "Not available" : Number(data.metrics.units).toLocaleString("en-IN");
  $("admin-orders").textContent = data.metrics.orders_made ?? "Not available";
  $("admin-received").textContent = data.metrics.orders_delivered ?? data.metrics.orders_received ?? "Not available";
  $("admin-orders-pending").textContent = data.metrics.orders_pending ?? "Not available";
  $("admin-customers").textContent = data.customers ?? "Not available";
  const statuses = rows("order_status");
  const statusTotal = statuses.reduce((sum, item) => sum + Number(item.orders || 0), 0);
  $("order-status-list").innerHTML = statuses.length
    ? statuses.map(item => `<div class="status-row"><div><span class="status-pill">${item.order_status}</span><strong>${Number(item.orders).toLocaleString()}</strong></div><div class="status-bar"><i style="width:${statusTotal ? Math.max(2, Number(item.orders) / statusTotal * 100) : 0}%"></i></div></div>`).join("")
    : "<p class='muted'>No order status data available.</p>";
  const stock = data.stock_alerts || {};
  $("stock-out").textContent = stock.out_of_stock ?? "—";
  $("stock-low").textContent = stock.low_stock ?? "—";
  $("stock-total").textContent = stock.units_in_stock ?? "—";
  $("stock-alert-list").innerHTML = (stock.products || []).length
    ? stock.products.map(item => `<div class="stock-row"><span>${item.product}<small>${item.sku}</small></span><strong>${Number(item.stock).toLocaleString()} left</strong></div>`).join("")
    : "<p class='muted'>No low-stock products.</p>";
  const scope = currentUser.role === "admin"
    ? "all customer categories"
    : `${currentUser.department} category`;
  $("notice").textContent = data.rows === 0
    ? "No rows match the selected date range. Choose dates between 2022-01-01 and 2024-12-31."
    : `Showing ${scope}. Items purchased, product categories, channels, regions, and customer IDs are restricted to this view.`;
  chart("segments", data.segments.map(x => x.segment), data.segments.map(x => x.rows), ["#164b36","#4f9270","#9bc28c","#d8f36a"]);
  const trendMetric = data.trend_metric || "record_activity";
  const performanceRows = productPerformance.length ? productPerformance : data.products.map(x => ({product: x.product, value: x.rows}));
  const performanceLabel = trendMetric === "revenue_inr" ? "Revenue by product (INR)" : trendMetric === "units_sold" ? "Units by product" : "Activity records by product";
  $("product-performance-label").textContent = performanceLabel;
  chart("product-performance", performanceRows.map(x => x.product), performanceRows.map(x => x.value), ["#164b36","#4f9270","#9bc28c","#d8f36a"], "bar", {scales: {y: {beginAtZero: true}}});
  $("trend-label").textContent = trendMetric === "record_activity" ? "Monthly activity; projection is a row-count proxy" : `Monthly ${trendMetric.replace("_", " ")} with projection`;
  lineChart("sales-trend", monthlyTrend.map(x => x.month), monthlyTrend.map(x => x.actual), monthlyTrend.map(x => x.predicted));
  $("revenue-trend-label").textContent = trendMetric === "record_activity" ? "Revenue unavailable; showing monthly activity" : `Monthly ${trendMetric.replace("_", " ")}`;
  lineChart("revenue-trend", monthlyTrend.map(x => x.month), monthlyTrend.map(x => x.actual), []);
  const dimensionChart = (id, values, type = "bar") => chart(id, values.map(x => x.dimension), values.map(x => x.value), ["#164b36", "#4f9270", "#9bc28c", "#d8f36a", "#f2a65a"], type, {scales: {y: {beginAtZero: true}}});
  dimensionChart("regions", regions);
  dimensionChart("customer-types", customerTypes, "doughnut");
  dimensionChart("pack-types", packTypes);
}
function makeTable(id, rows) {
  const table = $(id); table.innerHTML = "";
  if (!rows.length) { table.innerHTML = "<tr><td class='empty'>No data available.</td></tr>"; return; }
  const columns = Object.keys(rows[0]);
  const editable = false;
  const escape = value => String(value ?? "—").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  table.innerHTML = `<thead><tr>${columns.filter(x => x !== "_record_id").map(x => `<th>${x.replaceAll("_"," ")}</th>`).join("")}${editable ? "<th>Actions</th>" : ""}</tr></thead><tbody>${rows.map(row => `<tr data-record-id="${escape(row._record_id)}">${columns.filter(x => x !== "_record_id").map(x => `<td>${editable ? `<input class="edit-cell" data-field="${x}" value="${escape(row[x])}">` : escape(row[x])}</td>`).join("")}${editable ? "<td><button class='save-row'>Save</button></td>" : ""}</tr>`).join("")}</tbody>`;
  if (editable) {
    table.querySelectorAll(".save-row").forEach(button => button.addEventListener("click", async () => {
      const row = button.closest("tr");
      const updates = {};
      row.querySelectorAll(".edit-cell").forEach(input => { updates[input.dataset.field] = input.value; });
      const response = await fetch(`/api/admin/sales/${row.dataset.recordId}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify(updates)});
      button.textContent = response.ok ? "Saved" : "Retry";
    }));
  }
}
async function loadSales() { const response = await fetch("/api/sales"); if (response.status === 401) { window.location.href = "/login"; return; } const data = await response.json(); $("sales-access").textContent = currentUser.role === "admin" ? "All categories" : `Customer: ${currentUser.customer_id}`; makeTable("sales-table", data.rows); }
async function loadUserSales() { const response = await fetch("/api/sales"); if (response.ok) makeTable("user-sales-table", (await response.json()).rows); }
async function loadOrderOptions() {
  const response = await fetch("/api/order-options");
  if (!response.ok) return;
  const data = await response.json();
  $("order-product").innerHTML = data.products.map(product => `<option value="${product.sku}">${product.product_name} · ${product.pack_type} · ${money(product.price_unit_inr)}</option>`).join("");
}
async function loadQuality() { const data = await fetch("/api/quality").then(r => r.json()); $("quality-count").textContent = `${data.sales.length} columns`; makeTable("quality-table", data.sales); }
async function loadUsers() {
  const response = await fetch("/api/admin/users");
  if (!response.ok) return;
  const data = await response.json();
  makeTable("users-table", data.users);
}
document.querySelectorAll(".nav-link").forEach(button => button.addEventListener("click", async () => { document.querySelectorAll(".nav-link").forEach(x => x.classList.remove("active")); button.classList.add("active"); document.querySelectorAll(".page-section").forEach(x => x.classList.add("hidden")); $(button.dataset.section).classList.remove("hidden"); if (button.dataset.section === "sales") await loadSales(); if (button.dataset.section === "quality") await loadQuality(); if (button.dataset.section === "admin-users") await loadUsers(); }));
$("apply").addEventListener("click", loadDashboard);
async function initialize() {
  const response = await fetch("/api/me");
  if (!response.ok) { window.location.href = "/login"; return; }
  currentUser = await response.json();
  $("user-name").textContent = `${currentUser.username} (${currentUser.role}${currentUser.department ? ` · ${currentUser.department}` : ""})`;
  if (currentUser.role === "admin") {
    document.querySelectorAll(".admin-only").forEach(element => element.classList.remove("hidden"));
    $("dashboard-title").textContent = "NutriFuel Admin dashboard";
    $("dashboard-subtitle").textContent = "Full access to all customer accounts, analytics, data quality, and account management.";
  } else {
    $("admin-kpis").classList.add("hidden");
    $("admin-analytics").classList.add("hidden");
    document.querySelector(".date-filter").classList.add("hidden");
    document.querySelector('[data-section="sales"]').classList.add("hidden");
    document.querySelectorAll("#overview > .cards, #overview > .grid").forEach(element => element.classList.add("hidden"));
    $("user-dashboard").classList.remove("hidden");
    $("dashboard-title").textContent = `${currentUser.department} dashboard`;
    $("dashboard-subtitle").textContent = "Personal order and payment summary. Data is read-only.";
  }
  loadDashboard().then(async () => {
    if (currentUser.role !== "admin") {
      await loadOrderOptions();
      await loadUserSales();
    }
  }).catch(error => { $("notice").textContent = `Could not load dashboard data: ${error.message}`; });
}
$("logout").addEventListener("click", async () => { await fetch("/api/logout", {method: "POST"}); window.location.href = "/login"; });
if ($("user-form")) $("user-form").addEventListener("submit", async event => {
  event.preventDefault();
  const message = $("user-message");
  const response = await fetch("/api/admin/users", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({username: $("new-username").value, password: $("new-password").value, customer_id: $("new-customer-id").value, department: $("new-department").value})});
  const data = await response.json();
  message.textContent = response.ok ? `Created ${data.username}.` : (data.error || "Could not create user.");
  if (response.ok) { event.target.reset(); await loadUsers(); }
});
initialize();
if ($("order-form")) $("order-form").addEventListener("submit", async event => {
  event.preventDefault();
  const message = $("order-message");
  const response = await fetch("/api/orders", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({sku: $("order-product").value, quantity: $("order-quantity").value})});
  const data = await response.json().catch(() => ({}));
  message.textContent = response.ok ? `Order ${data.order.order_id} placed and marked pending.` : (data.error || "Could not place order.");
  if (response.ok) { $("order-quantity").value = 1; await loadDashboard(); await loadUserSales(); }
});
