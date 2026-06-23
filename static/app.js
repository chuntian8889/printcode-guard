let currentOrderId = null;

function el(id) { return document.getElementById(id); }

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }
  return res.json();
}

el("btn-save-scanner").onclick = async () => {
  const device = el("scanner-device").value.trim();
  try {
    await fetchJson("/api/scanner/device", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device: device || null }),
    });
    alert("扫描头配置已保存，请重启服务生效");
  } catch (e) {
    alert("保存失败: " + e.message);
  }
};

el("btn-new-order").onclick = async () => {
  const name = prompt("订单名称:");
  if (!name) return;
  const order = await fetchJson("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  currentOrderId = order.id;
  updateStatus();
};

el("btn-import").onclick = () => el("file-import").click();
el("file-import").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file || !currentOrderId) return alert("请先创建订单");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/orders/${currentOrderId}/import`, {
    method: "POST",
    body: form,
  });
  const json = await res.json();
  if (!res.ok) return alert("导入失败: " + JSON.stringify(json));
  alert(`成功导入 ${json.imported} 条码`);
};

el("btn-start").onclick = () =>
  fetchJson("/api/detection/start", { method: "POST" }).then(updateStatus);
el("btn-stop").onclick = () =>
  fetchJson("/api/detection/stop", { method: "POST" }).then(updateStatus);
el("btn-clear-alarm").onclick = () =>
  fetchJson("/api/alarm/clear", { method: "POST" }).then(updateStatus);
el("btn-test-buzzer").onclick = async () => {
  try {
    const data = await fetchJson("/api/buzzer/test", { method: "POST" });
    alert(`蜂鸣器测试已触发，后端：${data.backend}`);
  } catch (e) {
    alert("蜂鸣器测试失败: " + e.message);
  }
};

async function updateStatus() {
  let s;
  try {
    s = await fetchJson("/api/status");
  } catch (e) {
    console.error(e);
    return;
  }
  el("order-name").textContent = s.current_order ? s.current_order.name : "-";
  el("run-state").textContent = s.is_running ? "运行中" : "停止";
  el("total-count").textContent = s.total_scanned;
  el("dup-count").textContent = s.duplicate_count;
  el("err-count").textContent = s.abnormal_count;
  el("latest-code").textContent = s.latest_code || "-";
  el("scanner-device-display").textContent = s.scanner_device || "-";
  el("scanner-online").textContent = s.scanner_online ? "在线" : "离线";
  el("scanner-device-status").textContent = s.scanner_device || "-";
  el("scanner-online-status").textContent = s.scanner_online ? "在线" : "离线";
  el("scanner-error-status").textContent = s.scanner_error || "无";
  el("buzzer-backend").textContent = s.buzzer_backend || "-";
  if (s.current_order) currentOrderId = s.current_order.id;
  if (s.scanner_device) el("scanner-device").value = s.scanner_device;
  if (s.alarm_active) {
    document.body.classList.add("alarming");
    playBeep();
  } else {
    document.body.classList.remove("alarming");
  }
}

async function updateLists() {
  let scans, alarms;
  try {
    [scans, alarms] = await Promise.all([
      fetchJson("/api/scans"),
      fetchJson("/api/alarms"),
    ]);
  } catch (e) {
    console.error(e);
    return;
  }
  el("scan-list").innerHTML = scans
    .map(
      (r) =>
        `<li>${new Date(r.read_at).toLocaleTimeString()} — ${r.content} ` +
        `<span class="${r.is_abnormal ? "alarm" : ""}">${r.result_status}</span></li>`
    )
    .join("");
  el("alarm-list").innerHTML = alarms
    .map(
      (a) =>
        `<li class="alarm">${new Date(a.alarm_at).toLocaleTimeString()} — ` +
        `[${a.alarm_type}] ${a.content}</li>`
    )
    .join("");
}

function playBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    osc.type = "square";
    osc.frequency.value = 880;
    const gain = ctx.createGain();
    gain.gain.value = 0.1;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.2);
  } catch (e) {
    console.error("播放声音失败", e);
  }
}

setInterval(() => {
  updateStatus();
  updateLists();
}, 1000);
updateStatus();
updateLists();
