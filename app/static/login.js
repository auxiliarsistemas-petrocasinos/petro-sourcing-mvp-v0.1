const loginForm = document.querySelector("#loginForm");
const usernameEl = document.querySelector("#username");
const passwordEl = document.querySelector("#password");
const loginButton = document.querySelector("#loginButton");
const loginError = document.querySelector("#loginError");

function renderLoginIcons() {
  if (window.lucide) {
    window.lucide.createIcons({
      attrs: {
        "stroke-width": 1.8,
      },
    });
  }
}

function showLoginError(message) {
  loginError.textContent = message;
  loginError.classList.remove("hidden");
}

function clearLoginError() {
  loginError.textContent = "";
  loginError.classList.add("hidden");
}

function setLoginLoading(loading) {
  loginButton.disabled = loading;

  loginButton.querySelector("span").textContent =
    loading
      ? "Ingresando..."
      : "Iniciar sesión";
}

loginForm.addEventListener(
  "submit",
  async (event) => {
    event.preventDefault();
    clearLoginError();

    const username = usernameEl.value
      .trim()
      .toLowerCase();

    const password = passwordEl.value;

    if (!username || !password) {
      showLoginError(
        "Ingresa tu usuario y contraseña.",
      );
      return;
    }

    setLoginLoading(true);

    try {
      const response = await fetch(
        "/api/auth/login",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username,
            password,
          }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        throw new Error(
          body.detail ||
            "No fue posible iniciar sesión.",
        );
      }

      window.location.replace("/");
    } catch (error) {
      showLoginError(
        error.message ||
          "No fue posible iniciar sesión.",
      );
      passwordEl.select();
    } finally {
      setLoginLoading(false);
    }
  },
);

usernameEl.addEventListener(
  "input",
  clearLoginError,
);

passwordEl.addEventListener(
  "input",
  clearLoginError,
);

renderLoginIcons();
usernameEl.focus();
