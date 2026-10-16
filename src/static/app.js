document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const signupContainer = document.getElementById("signup-container");
  const messageDiv = document.getElementById("message");
  const accountButton = document.getElementById("account-button");
  const accountMenu = document.getElementById("account-menu");
  const accountStatus = document.getElementById("account-status");
  const loginButton = document.getElementById("login-button");
  const logoutButton = document.getElementById("logout-button");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const loginMessage = document.getElementById("login-message");
  const submitLoginButton = document.getElementById("submit-login");
  let isTeacher = false;

  function showMessage(element, text, type) {
    element.textContent = text;
    element.className = `message ${type}`;
    element.classList.remove("hidden");
    setTimeout(() => element.classList.add("hidden"), 5000);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>\"']/g, (character) => {
      const entities = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '\"': "&quot;",
        "'": "&#39;",
      };
      return entities[character];
    });
  }

  async function updateAccountState() {
    const response = await fetch("/auth/session");
    if (!response.ok) {
      throw new Error("Unable to check teacher login.");
    }
    const session = await response.json();
    isTeacher = session.authenticated;
    signupContainer.classList.toggle("hidden", !isTeacher);
    accountStatus.textContent = isTeacher ? `Signed in as ${session.username}` : "";
    accountStatus.classList.toggle("hidden", !isTeacher);
    loginButton.classList.toggle("hidden", isTeacher);
    logoutButton.classList.toggle("hidden", !isTeacher);
  }

  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) {
        throw new Error("Unable to load activities.");
      }
      const activities = await response.json();

      activitiesList.innerHTML = "";
      activitySelect.replaceChildren(new Option("-- Select an activity --", ""));

      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft =
          details.max_participants - details.participants.length;
        const participantsHTML =
          details.participants.length > 0
            ? `<div class="participants-section">
                <h5>Participants:</h5>
                <ul class="participants-list">
                  ${details.participants
                    .map((email) => {
                      const unregisterButton = isTeacher
                        ? `<button class="delete-btn" type="button"
                            data-activity="${escapeHtml(name)}"
                            data-email="${escapeHtml(email)}"
                            aria-label="Unregister ${escapeHtml(email)}">Remove</button>`
                        : "";
                      return `<li><span class="participant-email">${escapeHtml(email)}</span>${unregisterButton}</li>`;
                    })
                    .join("")}
                </ul>
              </div>`
            : "<p><em>No participants yet</em></p>";

        activityCard.innerHTML = `
          <h4>${escapeHtml(name)}</h4>
          <p>${escapeHtml(details.description)}</p>
          <p><strong>Schedule:</strong> ${escapeHtml(details.schedule)}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-container">${participantsHTML}</div>
        `;
        activitiesList.appendChild(activityCard);

        activitySelect.add(new Option(name, name));
      });

      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      activitiesList.textContent = "Failed to load activities. Please try again later.";
      console.error("Error fetching activities:", error);
    }
  }

  async function handleUnregister(event) {
    const button = event.currentTarget;
    const activity = button.getAttribute("data-activity");
    const email = button.getAttribute("data-email");
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/unregister?email=${encodeURIComponent(email)}`,
        { method: "DELETE" }
      );
      const result = await response.json();
      if (!response.ok) {
        if (response.status === 401) {
          await updateAccountState();
        }
        throw new Error(result.detail || "An error occurred");
      }
      showMessage(messageDiv, result.message, "success");
      await fetchActivities();
    } catch (error) {
      showMessage(messageDiv, error.message || "Failed to unregister. Please try again.", "error");
    }
  }

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value;
    const activity = activitySelect.value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/signup?email=${encodeURIComponent(email)}`,
        { method: "POST" }
      );
      const result = await response.json();
      if (!response.ok) {
        if (response.status === 401) {
          await updateAccountState();
        }
        throw new Error(result.detail || "An error occurred");
      }
      showMessage(messageDiv, result.message, "success");
      signupForm.reset();
      await fetchActivities();
    } catch (error) {
      showMessage(messageDiv, error.message || "Failed to sign up. Please try again.", "error");
    }
  });

  accountButton.addEventListener("click", () => {
    const isExpanded = accountButton.getAttribute("aria-expanded") === "true";
    accountButton.setAttribute("aria-expanded", String(!isExpanded));
    accountMenu.classList.toggle("hidden", isExpanded);
  });

  loginButton.addEventListener("click", () => {
    accountMenu.classList.add("hidden");
    accountButton.setAttribute("aria-expanded", "false");
    loginMessage.classList.add("hidden");
    loginForm.reset();
    loginDialog.showModal();
    document.getElementById("username").focus();
  });

  document.getElementById("cancel-login").addEventListener("click", () => {
    loginDialog.close();
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitLoginButton.disabled = true;
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Unable to log in.");
      }
      await updateAccountState();
      loginDialog.close();
      await fetchActivities();
    } catch (error) {
      showMessage(loginMessage, error.message || "Unable to log in.", "error");
    } finally {
      submitLoginButton.disabled = false;
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      if (!response.ok) {
        throw new Error("Unable to log out.");
      }
      await updateAccountState();
      accountMenu.classList.add("hidden");
      accountButton.setAttribute("aria-expanded", "false");
      signupForm.reset();
      await fetchActivities();
    } catch (error) {
      showMessage(messageDiv, error.message || "Unable to log out.", "error");
    }
  });

  async function initialize() {
    try {
      await updateAccountState();
    } catch (error) {
      console.error(error);
      showMessage(messageDiv, "Unable to check teacher login. Reload the page to try again.", "error");
    }
    await fetchActivities();
  }

  initialize();
});
