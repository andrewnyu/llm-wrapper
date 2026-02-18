const app = document.getElementById("image-app");
const promptInput = document.getElementById("image-prompt");
const generateButton = document.getElementById("generate");
const imageGrid = document.getElementById("image-grid");
const imageStatus = document.getElementById("image-status");
const emptyState = document.getElementById("image-empty");

function getCsrfToken() {
  const fromData = app?.dataset?.csrfToken;
  if (fromData) return fromData;
  const cookie = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith("csrftoken="));
  return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
}

function setStatus(text) {
  if (!text) {
    imageStatus.textContent = "";
    imageStatus.classList.add("hidden");
    return;
  }
  imageStatus.textContent = text;
  imageStatus.classList.remove("hidden");
}

function autosizeInput() {
  promptInput.style.height = "auto";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 180)}px`;
}

function ensureNotEmpty() {
  if (emptyState) {
    emptyState.remove();
  }
}

function addImage(urlOrBase64) {
  ensureNotEmpty();
  const card = document.createElement("figure");
  card.className = "image-card";

  const img = document.createElement("img");
  img.src = urlOrBase64;
  img.alt = "Generated image";
  card.appendChild(img);
  imageGrid.prepend(card);
}

async function generateImage() {
  const prompt = promptInput.value.trim();
  if (!prompt || generateButton.disabled) return;

  generateButton.disabled = true;
  setStatus("Generating image...");
  try {
    const response = await fetch("/api/image/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ prompt }),
      credentials: "same-origin",
    });
    const data = await response.json();
    if (!response.ok) {
      setStatus(data.error || "Request failed");
      return;
    }

    (data.images || []).forEach((image) => {
      if (image.url) addImage(image.url);
      else if (image.base64) addImage(image.base64);
    });
    promptInput.value = "";
    autosizeInput();
    setStatus("Image generated.");
    window.setTimeout(() => setStatus(""), 1400);
  } catch (_error) {
    setStatus("Network error");
  } finally {
    generateButton.disabled = false;
  }
}

generateButton.addEventListener("click", generateImage);
promptInput.addEventListener("input", autosizeInput);
promptInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await generateImage();
  }
});

autosizeInput();
