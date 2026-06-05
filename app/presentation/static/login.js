const form = document.querySelector("#login-form");
const message = document.querySelector("#login-message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = form.querySelector("button");
  submitButton.disabled = true;
  message.className = "result hidden";
  const formData = new FormData(form);

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
  message.className = "result error";
  message.textContent = body.detail || "Đăng nhập thất bại.";
  submitButton.disabled = false;
});
