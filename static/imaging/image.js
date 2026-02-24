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

function addAssistantBubble({ text = "", images = [], pending = false } = {}) {
  ensureNotEmpty();
  const message = document.createElement("div");
  message.className = "image-message assistant";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble assistant";

  const head = document.createElement("div");
  head.className = "assistant-head";

  const role = document.createElement("span");
  role.className = "message-role";
  role.textContent = "Nano Banana";
  head.appendChild(role);

  const model = document.createElement("span");
  model.className = "model-chip";
  model.textContent = "Gemini 2.5 Flash Image";
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
    sourceStatus.textContent = sourceType === "upload" ? "Mode: Edit (uploaded source)" : "Mode: Edit (selected image)";
    clearSourceButton.classList.remove("hidden");
  } else {
    generateButton.title = "Generate image";
    sourceStatus.textContent = "Mode: Generate";
    clearSourceButton.classList.add("hidden");
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
  if (!prompt || generateButton.disabled) return;

  generateButton.disabled = true;
  const isEdit = Boolean(selectedSourceImage);
  const requestSource = isEdit ? selectedSourceImage : null;
  addUserBubble(prompt, requestSource);
  const pendingBubble = addAssistantBubble({ pending: true });
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
    const data = await parseApiResponse(response);
    if (!response.ok) {
      const errorMessage = formatRequestError(response, data);
      pendingBubble.remove();
      addErrorBubble(errorMessage);
      setStatus(errorMessage);
      return;
    }

    const images = (data.images || [])
      .map((image) => image.url || image.base64)
      .filter(Boolean);
    pendingBubble.remove();
    addAssistantBubble({ text: data.text || "", images });

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

imageThread.addEventListener("click", (event) => {
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
scrollToLatestImage();
