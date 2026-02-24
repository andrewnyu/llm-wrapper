const app = document.getElementById("feedback-app");
const promptInput = document.getElementById("feedback-prompt");
const sendButton = document.getElementById("feedback-send");
const thread = document.getElementById("feedback-thread");
const status = document.getElementById("feedback-status");
const emptyState = document.getElementById("feedback-empty");
const pickSourceButton = document.getElementById("feedback-pick-source");
const clearSourceButton = document.getElementById("feedback-clear-source");
const sourceStatus = document.getElementById("feedback-source-status");
const sourceUpload = document.getElementById("feedback-source-upload");
const presetButtons = document.querySelectorAll(".preset-btn");

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
    status.textContent = "";
    status.classList.add("hidden");
    return;
  }
  status.textContent = text;
  status.classList.remove("hidden");
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

function scrollToLatest() {
  thread.scrollTop = thread.scrollHeight;
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

function addUserBubble(prompt, sourceImage) {
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
    sourceLabel.textContent = "Attached image";

    const sourcePreview = document.createElement("img");
    sourcePreview.className = "message-source-thumb";
    sourcePreview.src = sourceImage;
    sourcePreview.alt = "Uploaded source image";

    sourceWrap.appendChild(sourceLabel);
    sourceWrap.appendChild(sourcePreview);
    bubble.appendChild(sourceWrap);
  }

  bubble.appendChild(buildMessageMeta());
  message.appendChild(bubble);
  thread.appendChild(message);
  scrollToLatest();
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
    thread.appendChild(message);
    scrollToLatest();
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

    const image = document.createElement("img");
    image.src = imageSrc;
    image.alt = "Feedback result image";
    image.className = "editable-image";
    card.appendChild(image);
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
  thread.appendChild(message);
  scrollToLatest();
  return message;
}

function addErrorBubble(messageText) {
  const message = document.createElement("div");
  message.className = "image-message assistant";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble assistant error";
  bubble.textContent = messageText;
  message.appendChild(bubble);

  thread.appendChild(message);
  scrollToLatest();
}

function setSelectedSource(src, sourceType = "upload") {
  selectedSourceImage = src || null;
  if (selectedSourceImage) {
    sendButton.title = "Send image feedback request";
    sourceStatus.textContent = sourceType === "selected" ? "Image: selected from thread" : "Image: uploaded";
    clearSourceButton.classList.remove("hidden");
  } else {
    sendButton.title = "Send feedback request";
    sourceStatus.textContent = "Image: none selected";
    clearSourceButton.classList.add("hidden");
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

async function runFeedbackRequest() {
  if (sendButton.disabled) return;
  if (!selectedSourceImage) {
    setStatus("Upload an image first.");
    return;
  }

  const prompt = promptInput.value.trim();
  const displayPrompt = prompt || "Analyze this image: description, spelling issues, and comments.";

  sendButton.disabled = true;
  addUserBubble(displayPrompt, selectedSourceImage);
  const pendingBubble = addAssistantBubble({ pending: true });
  setStatus("Analyzing image...");

  try {
    const response = await fetch("/api/image/feedback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ prompt, input_image: selectedSourceImage }),
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

    pendingBubble.remove();
    const images = (data.images || [])
      .map((image) => image.url || image.base64)
      .filter(Boolean);
    addAssistantBubble({ text: data.text || "", images });

    promptInput.value = "";
    autosizeInput();
    setStatus("Feedback ready.");
    window.setTimeout(() => setStatus(""), 1400);
  } catch (_error) {
    pendingBubble.remove();
    addErrorBubble("Network error. Please retry.");
    setStatus("Network error. Please retry.");
  } finally {
    sendButton.disabled = false;
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
    setStatus("Image uploaded. Ask for feedback.");
    window.setTimeout(() => setStatus(""), 1400);
  };
  reader.onerror = () => setStatus("Could not read selected image");
  reader.readAsDataURL(file);
  sourceUpload.value = "";
});

thread.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLImageElement)) return;
  if (!target.classList.contains("editable-image")) return;
  setSelectedSource(target.src, "selected");
  setStatus("Selected image from thread.");
  window.setTimeout(() => setStatus(""), 1200);
});

presetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt || "";
    autosizeInput();
    promptInput.focus();
  });
});

sendButton.addEventListener("click", runFeedbackRequest);
promptInput.addEventListener("input", autosizeInput);
promptInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    await runFeedbackRequest();
  }
});

autosizeInput();
scrollToLatest();
