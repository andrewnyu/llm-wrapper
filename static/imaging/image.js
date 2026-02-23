const app = document.getElementById("image-app");
const promptInput = document.getElementById("image-prompt");
const generateButton = document.getElementById("generate");
const imageGrid = document.getElementById("image-grid");
const imageStatus = document.getElementById("image-status");
const emptyState = document.getElementById("image-empty");
const pickSourceButton = document.getElementById("pick-source");
const clearSourceButton = document.getElementById("clear-source");
const sourceStatus = document.getElementById("source-status");
const sourceUpload = document.getElementById("source-upload");

let selectedSourceImage = null;

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
  img.className = "editable-image";
  card.appendChild(img);
  imageGrid.prepend(card);
}

function clearSelectedCard() {
  document.querySelectorAll(".image-card.selected").forEach((card) => {
    card.classList.remove("selected");
  });
}

function setSelectedSource(src, sourceType = "selected") {
  selectedSourceImage = src || null;
  if (selectedSourceImage) {
    generateButton.title = "Edit selected image";
    sourceStatus.textContent = sourceType === "upload" ? "Mode: Edit (uploaded source)" : "Mode: Edit (selected image)";
    clearSourceButton.classList.remove("hidden");
  } else {
    generateButton.title = "Generate image";
    sourceStatus.textContent = "Mode: Generate";
    clearSourceButton.classList.add("hidden");
    clearSelectedCard();
  }
}

async function runImageRequest() {
  const prompt = promptInput.value.trim();
  if (!prompt || generateButton.disabled) return;

  generateButton.disabled = true;
  const isEdit = Boolean(selectedSourceImage);
  setStatus(isEdit ? "Editing image..." : "Generating image...");
  try {
    const response = await fetch(isEdit ? "/api/image/edit" : "/api/image/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(
        isEdit ? { prompt, input_image: selectedSourceImage } : { prompt },
      ),
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
    setStatus(isEdit ? "Image edited." : "Image generated.");
    setSelectedSource(null);
    window.setTimeout(() => setStatus(""), 1400);
  } catch (_error) {
    setStatus("Network error");
  } finally {
    generateButton.disabled = false;
  }
}

pickSourceButton.addEventListener("click", () => {
  sourceUpload.click();
});

clearSourceButton.addEventListener("click", () => {
  setSelectedSource(null);
});

sourceUpload.addEventListener("change", () => {
  const file = sourceUpload.files && sourceUpload.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const source = typeof reader.result === "string" ? reader.result : null;
    if (!source) {
      setStatus("Could not read selected image");
      return;
    }
    setSelectedSource(source, "upload");
    setStatus("Source image loaded. Enter a prompt to edit it.");
    window.setTimeout(() => setStatus(""), 1400);
  };
  reader.onerror = () => setStatus("Could not read selected image");
  reader.readAsDataURL(file);
  sourceUpload.value = "";
});

imageGrid.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLImageElement)) return;
  if (!target.classList.contains("editable-image")) return;

  const card = target.closest(".image-card");
  if (!card) return;

  clearSelectedCard();
  card.classList.add("selected");
  setSelectedSource(target.src, "selected");
  setStatus("Image selected. Enter a prompt to edit it.");
  window.setTimeout(() => setStatus(""), 1400);
});

generateButton.addEventListener("click", runImageRequest);
promptInput.addEventListener("input", autosizeInput);
promptInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await runImageRequest();
  }
});

autosizeInput();
