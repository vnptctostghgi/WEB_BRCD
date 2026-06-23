const form = document.querySelector("#login-form");
const message = document.querySelector("#login-message");
const rememberLogin = document.querySelector("#remember-login");
const usernameInput = form.elements.namedItem("username");

const rememberedUsername = localStorage.getItem("brcd_remember_username");
if (rememberedUsername) {
  usernameInput.value = rememberedUsername;
  rememberLogin.checked = true;
}

function safeNextPath() {
  const next = new URLSearchParams(window.location.search).get("next") || "/";
  if (!next.startsWith("/") || next.startsWith("//")) return "/";
  return next;
}

function showMessage(text, type = "error") {
  message.className = `result ${type}`;
  message.textContent = text;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = form.querySelector("button[type='submit']");
  submitButton.disabled = true;
  submitButton.classList.add("loading");
  message.className = "result hidden";
  const formData = new FormData(form);
  if (rememberLogin.checked) {
    localStorage.setItem("brcd_remember_username", String(formData.get("username") || ""));
  } else {
    localStorage.removeItem("brcd_remember_username");
  }

  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: formData.get("username"),
        password: formData.get("password"),
      }),
    });

    if (response.ok) {
      window.location.href = safeNextPath();
      return;
    }
    const body = await response.json();
    showMessage(body.detail || "Đăng nhập thất bại.");
  } catch {
    showMessage("Không kết nối được máy chủ. Vui lòng thử lại.");
  } finally {
    submitButton.disabled = false;
    submitButton.classList.remove("loading");
  }
});
