// Toast notifications
function toast(msg, type = "success") {
  const container =
    document.getElementById("toast-container") ||
    (() => {
      const d = document.createElement("div");
      d.id = "toast-container";
      document.body.appendChild(d);
      return d;
    })();
  const icons = { success: "✓", error: "✕", warning: "⚠" };
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || "•"}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

// API helper
async function api(method, url, body = null, isForm = false) {
  const opts = { method, headers: {}, credentials: "include" };
  if (body) {
    if (isForm) {
      opts.body = body;
    } else {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
  return data;
}

// Format date
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Format time remaining
function fmtTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0)
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Loading state on button
function setLoading(btn, loading) {
  if (loading) {
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span> Loading…';
    btn.disabled = true;
  } else {
    btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
    btn.disabled = false;
  }
}

// Logout
async function logout(role = "admin") {
  try {
    await fetch(`/api/${role}/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {}
  window.location.href =
    role === "admin"
      ? "/static/admin/login.html"
      : "/static/student/login.html";
}
