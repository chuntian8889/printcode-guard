let isSelecting = false;
let startX, startY, selectionBox;
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

el("btn-open").onclick = async () => {
  const url = el("rtsp-url").value.trim();
  if (!url) return alert("请输入 RTSP 地址");
  await fetchJson("/api/camera/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  el("video").src = "/api/camera/frame?" + Date.now();
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
  if (s.current_order) currentOrderId = s.current_order.id;
  if (s.rtsp_url) el("rtsp-url").value = s.rtsp_url;
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

// ROI 框选
const videoWrap = document.querySelector(".video-wrap");
videoWrap.onmousedown = (e) => {
  const rect = videoWrap.getBoundingClientRect();
  startX = e.clientX - rect.left;
  startY = e.clientY - rect.top;
  isSelecting = true;
  if (!selectionBox) {
    selectionBox = document.createElement("div");
    selectionBox.className = "selection-box";
    videoWrap.appendChild(selectionBox);
  }
  selectionBox.style.left = startX + "px";
  selectionBox.style.top = startY + "px";
  selectionBox.style.width = "0px";
  selectionBox.style.height = "0px";
  selectionBox.style.display = "block";
};

document.onmousemove = (e) => {
  if (!isSelecting || !selectionBox) return;
  const rect = videoWrap.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const w = Math.abs(x - startX);
  const h = Math.abs(y - startY);
  const left = Math.min(x, startX);
  const top = Math.min(y, startY);
  selectionBox.style.left = left + "px";
  selectionBox.style.top = top + "px";
  selectionBox.style.width = w + "px";
  selectionBox.style.height = h + "px";
};

document.onmouseup = async () => {
  if (!isSelecting || !selectionBox) return;
  isSelecting = false;
  const img = el("video");
  const wrapRect = videoWrap.getBoundingClientRect();
  const box = selectionBox.getBoundingClientRect();
  const displayW = wrapRect.width;
  const displayH = wrapRect.height;
  const naturalW = img.naturalWidth || displayW;
  const naturalH = img.naturalHeight || displayH;
  const scaleX = naturalW / displayW;
  const scaleY = naturalH / displayH;
  const x = Math.round((box.left - wrapRect.left) * scaleX);
  const y = Math.round((box.top - wrapRect.top) * scaleY);
  const w = Math.round(box.width * scaleX);
  const h = Math.round(box.height * scaleY);
  selectionBox.style.display = "none";
  try {
    await fetchJson("/api/camera/roi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ x, y, w, h }),
    });
    alert("ROI 已设置");
  } catch (e) {
    alert("设置 ROI 失败: " + e.message);
  }
};

setInterval(() => {
  updateStatus();
  updateLists();
}, 1000);
updateStatus();
