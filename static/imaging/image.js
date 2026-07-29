const app = document.getElementById("image-app");
const promptInput = document.getElementById("image-prompt");
const generateButton = document.getElementById("generate");
const imageThread = document.getElementById("image-thread");
const imageStatus = document.getElementById("image-status");
const emptyState = document.getElementById("image-empty");
const pickSourceButton = document.getElementById("pick-source");
const clearSourceButton = document.getElementById("clear-source");
const sourceStatus = document.getElementById("source-status");
const sourceUpload = document.getElementById("source-upload");
const sourcePreview = document.getElementById("source-preview");
const sourcePreviewImage = document.getElementById("source-preview-image");
const imageComposer = document.getElementById("image-composer");
const modelSelect = document.getElementById("image-model");
const aspectRatioSelect = document.getElementById("aspect-ratio");
const imageSizeSelect = document.getElementById("image-size");
const imageModels = JSON.parse(document.getElementById("image-models-data")?.textContent || "[]");

let selectedSourceImage = null;
let isGenerating = false;
const MAX_SOURCE_FILE_BYTES = 12 * 1024 * 1024;

function selectedModelConfig() {
  return imageModels.find((item) => item.model === modelSelect.value) || imageModels[0] || null;
}

function updateGenerateButton() {
  const model = selectedModelConfig();
  const canGenerate = Boolean(model?.configured && promptInput.value.trim());
  generateButton.disabled = isGenerating || !canGenerate;
  generateButton.setAttribute("aria-busy", isGenerating ? "true" : "false");
}

function fillSelect(select, values, preferred) {
  select.innerHTML = values.map((value) => `<option value="${value}">${value}</option>`).join("");
  select.value = values.includes(preferred) ? preferred : values[0] || "";
}

function refreshImageControls() {
  let model = selectedModelConfig();
  if (!model?.configured) {
    const fallback = imageModels.find((item) => item.configured);
    if (fallback) {
      modelSelect.value = fallback.model;
      model = fallback;
    }
  }
  if (!model?.configured) {
    modelSelect.disabled = true;
    aspectRatioSelect.disabled = true;
    imageSizeSelect.disabled = true;
    setStatus("No image model is configured on this server.");
    updateGenerateButton();
    return;
  }
  modelSelect.disabled = false;
  aspectRatioSelect.disabled = false;
  imageSizeSelect.disabled = false;
  fillSelect(
    aspectRatioSelect,
    model.aspect_ratios || ["1:1"],
    localStorage.getItem("image-aspect-ratio") || aspectRatioSelect.value || "1:1",
  );
  fillSelect(
    imageSizeSelect,
    model.resolutions || ["1K"],
    localStorage.getItem("image-size") || imageSizeSelect.value || "1K",
  );
  localStorage.setItem("image-model", model.model);
  updateGenerateButton();
}

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
  updateGenerateButton();
}

function ensureNotEmpty() {
  if (emptyState) {
    emptyState.remove();
  }
}

function scrollToLatestImage() {
  imageThread.scrollTop = imageThread.scrollHeight;
}

function formatNow() {
  return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function buildMessageMeta() {
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = formatNow();
  return meta;
}

function addUserBubble(prompt, sourceImage = null) {
  ensureNotEmpty();
  const message = document.createElement("div");
  message.className = "image-message user";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble user";

  const role = document.createElement("div");
  role.className = "message-role";
  role.textContent = "You";
  bubble.appendChild(role);

  const text = document.createElement("p");
  text.className = "message-text user-text";
  text.textContent = prompt;
  bubble.appendChild(text);

  if (sourceImage) {
    const sourceWrap = document.createElement("div");
    sourceWrap.className = "message-source-wrap";

    const sourceLabel = document.createElement("span");
    sourceLabel.className = "source-chip";
    sourceLabel.textContent = "Source image";

    const sourcePreview = document.createElement("img");
    sourcePreview.className = "message-source-thumb";
    sourcePreview.src = sourceImage;
    sourcePreview.alt = "Source image preview";

    sourceWrap.appendChild(sourceLabel);
    sourceWrap.appendChild(sourcePreview);
    bubble.appendChild(sourceWrap);
  }

  bubble.appendChild(buildMessageMeta());

  message.appendChild(bubble);
  imageThread.appendChild(message);
  scrollToLatestImage();
}

function addAssistantBubble({ text = "", images = [], pending = false, settings = {} } = {}) {
  ensureNotEmpty();
  const message = document.createElement("div");
  message.className = "image-message assistant";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble assistant";

  const head = document.createElement("div");
  head.className = "assistant-head";

  const avatar = document.createElement("span");
  avatar.className = "assistant-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = "✦";
  head.appendChild(avatar);

  const role = document.createElement("span");
  role.className = "message-role";
  role.textContent = settings.model_label || selectedModelConfig()?.label || "Nano Banana";
  head.appendChild(role);

  const model = document.createElement("span");
  model.className = "model-chip";
  model.textContent = `${settings.aspect_ratio || aspectRatioSelect.value} · ${settings.image_size || imageSizeSelect.value}`;
  head.appendChild(model);

  bubble.appendChild(head);

  if (pending) {
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    bubble.appendChild(typing);
    bubble.appendChild(buildMessageMeta());
    message.appendChild(bubble);
    imageThread.appendChild(message);
    scrollToLatestImage();
    return message;
  }

  const trimmed = typeof text === "string" ? text.trim() : "";
  if (trimmed) {
    const textNode = document.createElement("p");
    textNode.className = "message-text";
    textNode.textContent = trimmed;
    bubble.appendChild(textNode);
  }

  images.forEach((imageSrc) => {
    const card = document.createElement("figure");
    card.className = "image-card";

    const img = document.createElement("img");
    img.src = imageSrc;
    img.alt = "Generated image";
    img.className = "editable-image";
    card.appendChild(img);

    const actions = document.createElement("figcaption");
    actions.className = "image-card-actions";
    actions.innerHTML = `
      <button class="image-action edit-image" type="button">Edit this</button>
      <a class="image-action download-image" download="generated-image.png">Download</a>
    `;
    actions.querySelector(".download-image").href = imageSrc;
    card.appendChild(actions);
    bubble.appendChild(card);
  });

  if (!trimmed && images.length === 0) {
    const fallback = document.createElement("p");
    fallback.className = "message-text";
    fallback.textContent = "No content returned.";
    bubble.appendChild(fallback);
  }

  bubble.appendChild(buildMessageMeta());
  message.appendChild(bubble);
  imageThread.appendChild(message);
  scrollToLatestImage();
  return message;
}

function addErrorBubble(messageText) {
  const message = document.createElement("div");
  message.className = "image-message assistant";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble assistant error";
  bubble.textContent = messageText;
  message.appendChild(bubble);

  imageThread.appendChild(message);
  scrollToLatestImage();
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
    sourceStatus.textContent = sourceType === "upload" ? "Uploaded reference" : "Selected reference";
    sourcePreviewImage.src = selectedSourceImage;
    sourcePreview.classList.remove("hidden");
  } else {
    generateButton.title = "Generate image";
    sourceStatus.textContent = "New image";
    sourcePreviewImage.removeAttribute("src");
    sourcePreview.classList.add("hidden");
    clearSelectedCard();
  }
}

async function parseApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }
  try {
    const raw = await response.text();
    return { error: raw || "" };
  } catch (_error) {
    return {};
  }
}

function formatRequestError(response, data) {
  const serverError = typeof data?.error === "string" ? data.error : "";
  if (response.status === 413 || /RequestDataTooBig/i.test(serverError)) {
    return "Upload too large. Please use a smaller image.";
  }
  if (serverError) {
    return serverError.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  }
  return `Request failed (${response.status})`;
}

async function runImageRequest() {
  const prompt = promptInput.value.trim();
  if (!prompt || isGenerating || !selectedModelConfig()?.configured) {
    promptInput.focus();
    return;
  }

  isGenerating = true;
  updateGenerateButton();
  const isEdit = Boolean(selectedSourceImage);
  const requestSource = isEdit ? selectedSourceImage : null;
  const requestSettings = {
    model: modelSelect.value,
    model_label: selectedModelConfig()?.label || modelSelect.value,
    aspect_ratio: aspectRatioSelect.value,
    image_size: imageSizeSelect.value,
  };
  addUserBubble(prompt, requestSource);
  const pendingBubble = addAssistantBubble({ pending: true, settings: requestSettings });
  setStatus(isEdit ? "Editing image..." : "Generating image...");
  try {
    const response = await fetch(isEdit ? "/api/image/edit" : "/api/image/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(
        isEdit
          ? { prompt, input_image: selectedSourceImage, ...requestSettings }
          : { prompt, ...requestSettings },
      ),
      credentials: "same-origin",
    });
    const data = await parseApiResponse(response);
    if (!response.ok) {
      const errorMessage = formatRequestError(response, data);
      pendingBubble.remove();
      addErrorBubble(errorMessage);
      setStatus(errorMessage);
      return;
    }

    const images = (Array.isArray(data.images) ? data.images : [])
      .map((image) => (typeof image === "string" ? image : image?.url || image?.base64))
      .filter(Boolean);
    pendingBubble.remove();
    addAssistantBubble({ text: data.text || "", images, settings: data.settings || requestSettings });

    promptInput.value = "";
    autosizeInput();
    setStatus(
      data.text
        ? "Response ready."
        : isEdit
          ? "Image edited."
          : "Image generated.",
    );
    setSelectedSource(null);
    window.setTimeout(() => setStatus(""), 1400);
  } catch (_error) {
    pendingBubble.remove();
    addErrorBubble("Network error. Please retry.");
    setStatus("Network error. Please retry.");
  } finally {
    isGenerating = false;
    updateGenerateButton();
  }
}

pickSourceButton.addEventListener("click", () => {
  sourceUpload.click();
});

clearSourceButton.addEventListener("click", () => {
  setSelectedSource(null);
});

function loadSourceFile(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setStatus("Please choose an image file.");
    return;
  }
  if (file.size > MAX_SOURCE_FILE_BYTES) {
    setStatus("That image is too large. Choose a file under 12 MB.");
    return;
  }
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
}

sourceUpload.addEventListener("change", () => {
  const file = sourceUpload.files && sourceUpload.files[0];
  loadSourceFile(file);
  sourceUpload.value = "";
});

imageThread.addEventListener("click", (event) => {
  const editButton = event.target.closest(".edit-image");
  if (editButton) {
    const image = editButton.closest(".image-card")?.querySelector(".editable-image");
    if (image) {
      clearSelectedCard();
      image.closest(".image-card")?.classList.add("selected");
      setSelectedSource(image.src, "selected");
      promptInput.focus();
    }
    return;
  }
  if (event.target.closest(".download-image")) return;
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
modelSelect.addEventListener("change", () => {
  refreshImageControls();
  localStorage.setItem("image-model", modelSelect.value);
});
aspectRatioSelect.addEventListener("change", () => localStorage.setItem("image-aspect-ratio", aspectRatioSelect.value));
imageSizeSelect.addEventListener("change", () => localStorage.setItem("image-size", imageSizeSelect.value));
promptInput.addEventListener("input", autosizeInput);
promptInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await runImageRequest();
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt || "";
    autosizeInput();
    promptInput.focus();
  });
});

document.addEventListener("paste", (event) => {
  const imageItem = Array.from(event.clipboardData?.items || []).find((item) => item.type.startsWith("image/"));
  if (imageItem) loadSourceFile(imageItem.getAsFile());
});

document.addEventListener("dragover", (event) => {
  if (Array.from(event.dataTransfer?.items || []).some((item) => item.type.startsWith("image/"))) {
    event.preventDefault();
    imageComposer.classList.add("drag-active");
  }
});

document.addEventListener("dragleave", (event) => {
  if (!event.relatedTarget) imageComposer.classList.remove("drag-active");
});

document.addEventListener("drop", (event) => {
  const file = Array.from(event.dataTransfer?.files || []).find((item) => item.type.startsWith("image/"));
  if (!file) return;
  event.preventDefault();
  imageComposer.classList.remove("drag-active");
  loadSourceFile(file);
});
document.addEventListener("dragend", () => imageComposer.classList.remove("drag-active"));

const savedModel = localStorage.getItem("image-model");
if (savedModel && imageModels.some((item) => item.model === savedModel && item.configured)) {
  modelSelect.value = savedModel;
}
refreshImageControls();
autosizeInput();
scrollToLatestImage();
