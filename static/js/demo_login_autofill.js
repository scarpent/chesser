document.addEventListener("DOMContentLoaded", () => {
  const username = document.querySelector('input[name="username"]');
  const password = document.querySelector('input[name="password"]');
  const submit = document.querySelector('button[type="submit"]');

  if (!username || !password) return;

  // Only fill if empty (don’t override user input or browser autofill)
  if (!username.value) {
    username.value = "demo";
  }

  if (!password.value) {
    password.value = "demo";
  }

  // Override Django's username autofocus in demo mode
  if (submit) {
    submit.focus();
  }
});
