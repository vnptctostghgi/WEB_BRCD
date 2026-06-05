const form = document.querySelector("#login-form");
const message = document.querySelector("#login-message");
const themeToggle = document.querySelector("#theme-toggle");

function applyTheme(nextTheme) {
  document.documentElement.classList.toggle("dark", nextTheme === "dark");
  localStorage.theme = nextTheme;
  if (themeToggle) themeToggle.textContent = nextTheme === "dark" ? "Chế độ tối" : "Chế độ sáng";
}

applyTheme(localStorage.theme === "dark" ? "dark" : "light");

themeToggle?.addEventListener("click", () => {
  applyTheme(document.documentElement.classList.contains("dark") ? "light" : "dark");
});

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
      window.location.href = "/";
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
