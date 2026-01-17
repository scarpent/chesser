document.addEventListener("DOMContentLoaded", () => {
  const username = document.querySelector('input[name="username"]');
  const password = document.querySelector('input[name="password"]');
  const submit = document.querySelector('button[type="submit"]');

  // Demo convenience: these must match the credentials created by `manage.py seed_demo`.
  // Username/password are intentionally low-security because demo mode is read-only.
  const DEMO_USERNAME = "demo";
  const DEMO_PASSWORD = "demo";

  if (!username || !password) return;

  // Only fill if empty (don’t override user input or browser autofill)
  if (!username.value) {
    username.value = DEMO_USERNAME;
  }

  if (!password.value) {
    password.value = DEMO_PASSWORD;
  }

  // Override Django's username autofocus in demo mode
  if (submit) {
    submit.focus();
  }
});
