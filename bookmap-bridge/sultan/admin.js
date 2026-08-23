// Admin panel - setup/login/settings flow. Dadang: "lo beri admin panel
// aja lo bro nanti gw isi email dan pasword gw" - his own credentials, set
// up once via /api/admin/setup, checked every load via /api/admin/status.
// Session lives in an HttpOnly cookie the browser sends automatically -
// this file never touches the cookie value itself.

function show(id) {
  ["view-setup", "view-login", "view-settings", "loading-label"].forEach((v) => {
    document.getElementById(v).classList.toggle("hidden", v !== id);
  });
}

async function checkStatus() {
  try {
    const res = await fetch("/api/admin/status", { cache: "no-store" });
    const data = await res.json();
    if (!data.setup_done) {
      show("view-setup");
    } else if (!data.logged_in) {
      show("view-login");
    } else {
      show("view-settings");
      document.getElementById("logged-in-email").textContent = data.email || "";
    }
  } catch (e) {
    document.getElementById("loading-label").textContent = "Gagal konek ke server: " + String(e);
  }
}

document.getElementById("setup-submit").addEventListener("click", async () => {
  const errorEl = document.getElementById("setup-error");
  const email = document.getElementById("setup-email").value.trim();
  const password = document.getElementById("setup-password").value;
  const password2 = document.getElementById("setup-password2").value;
  errorEl.textContent = "";
  if (password !== password2) {
    errorEl.textContent = "Password gak sama";
    return;
  }
  try {
    const res = await fetch("/api/admin/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      checkStatus();
    } else {
      errorEl.textContent = data.error || "Gagal setup akun";
    }
  } catch (e) {
    errorEl.textContent = "Gagal konek ke server: " + String(e);
  }
});

document.getElementById("login-submit").addEventListener("click", async () => {
  const errorEl = document.getElementById("login-error");
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  errorEl.textContent = "";
  try {
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      checkStatus();
    } else {
      errorEl.textContent = data.error || "Login gagal";
    }
  } catch (e) {
    errorEl.textContent = "Gagal konek ke server: " + String(e);
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/api/admin/logout", { method: "POST" });
  checkStatus();
});

document.getElementById("settings-save").addEventListener("click", async () => {
  const statusEl = document.getElementById("settings-status");
  const payload = {
    api_key: document.getElementById("set-api-key").value.trim(),
    api_base: document.getElementById("set-api-base").value.trim(),
    model: document.getElementById("set-model").value.trim(),
    analysis_model: document.getElementById("set-analysis-model").value.trim(),
  };
  statusEl.textContent = "Menyimpan...";
  statusEl.className = "text-[11px] text-slate-500";
  try {
    const res = await fetch("/api/settings/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      statusEl.textContent = `Tersimpan: ${data.saved.join(", ")}`;
      statusEl.className = "text-[11px] text-emerald-400";
      document.getElementById("set-api-key").value = "";
    } else if (res.status === 401) {
      statusEl.textContent = "Sesi habis, login ulang.";
      statusEl.className = "text-[11px] text-rose-400";
      checkStatus();
    } else {
      statusEl.textContent = data.error || "Gagal menyimpan";
      statusEl.className = "text-[11px] text-rose-400";
    }
  } catch (e) {
    statusEl.textContent = "Gagal konek ke server: " + String(e);
    statusEl.className = "text-[11px] text-rose-400";
  }
});

checkStatus();
