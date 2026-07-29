const KIND = "studio";
const API = {
  conversations: `/api/image/conversations?kind=${KIND}`,
  conversationBase: "/api/image/conversations",
};

const app = document.getElementById("image-app");
const promptInput = document.getElementById("image-prompt");
const generateButton = document.getElementById("generate");
const imageThread = document.getElementById("image-thread");
const imageStatus = document.getElementById("image-status");
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
const chatTitle = document.getElementById("image-chat-title");
const newChatButton = document.getElementById("new-image-chat");
const conversationList = document.getElementById("image-conversation-list");
const imageModels = JSON.parse(document.getElementById("image-models-data")?.textContent || "[]");

const state = {
  conversations: [],
  activeConversationId: null,
  hasMoreJobs: false,
  oldestJobCursor: null,
  loadingJobs: false,
  loadingConversations: false,
};

let selectedSourceImage = null;
let isGenerating = false;
const MAX_SOURCE_FILE_BYTES = 12 * 1024 * 1024;

function selectedModelConfig() {
  return imageModels.find((item) => item.model === modelSelect.value) || imageModels[0] || null;
}

function selectedModelSupportsEdit() {
  return selectedModelConfig()?.supports_edit !== false;
}

function updateGenerateButton() {
  const model = selectedModelConfig();
  const canGenerate = Boolean(model?.configured && promptInput.value.trim() && (!selectedSourceImage || selectedModelSupportsEdit()));
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
  fillSelect(aspectRatioSelect, model.aspect_ratios || ["1:1"], localStorage.getItem("image-aspect-ratio") || aspectRatioSelect.value || "1:1");
  fillSelect(imageSizeSelect, model.resolutions || ["1K"], localStorage.getItem("image-size") || imageSizeSelect.value || "1K");
  localStorage.setItem("image-model", model.model);
  if (selectedSourceImage) setSelectedSource(selectedSourceImage);
  if (selectedSourceImage && !selectedModelSupportsEdit()) {
    setStatus(`${model.label} can generate images, but does not support reference edits.`);
  }
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

async function apiFetch(url, options = {}) {
  return fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
      ...(options.headers || {}),
    },
    ...options,
  });
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

function emptyMarkup() {
  return `
    <div id="image-empty" class="image-empty">
      <div class="empty-orbit" aria-hidden="true">✦</div>
      <h2>Bring an idea to life</h2>
      <p>Describe the result, add a reference if you have one, or start with an example.</p>
      <div class="prompt-starters">
        <button type="button" data-prompt="A premium studio product photo on a clean sculptural set, soft directional lighting, editorial composition">Product photo</button>
        <button type="button" data-prompt="A bold cinematic poster with striking typography, dramatic lighting, and a polished campaign aesthetic">Campaign poster</button>
        <button type="button" data-prompt="A charming illustrated scene with expressive characters, rich texture, and a warm storybook palette">Storybook scene</button>
      </div>
    </div>
  `;
}

function resetThread() {
  imageThread.innerHTML = emptyMarkup();
  bindPromptStarters();
  state.hasMoreJobs = false;
  state.oldestJobCursor = null;
}

function ensureNotEmpty() {
  document.getElementById("image-empty")?.remove();
}

function scrollToLatestImage() {
  imageThread.scrollTop = imageThread.scrollHeight;
}

function formatTime(value = null) {
  const date = value ? new Date(value) : new Date();
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatConversationTime(value) {
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return formatTime(value);
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function buildMessageMeta(value = null) {
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = formatTime(value);
  return meta;
}

function buildUserBubble(prompt, sourceImage = null, createdAt = null) {
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
    sourceWrap.append(sourceLabel, sourcePreview);
    bubble.appendChild(sourceWrap);
  }

  bubble.appendChild(buildMessageMeta(createdAt));
  message.appendChild(bubble);
  return message;
}

function buildAssistantBubble({ text = "", images = [], pending = false, settings = {}, createdAt = null } = {}) {
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
  const role = document.createElement("span");
  role.className = "message-role";
  role.textContent = settings.model_label || selectedModelConfig()?.label || "Image model";
  const model = document.createElement("span");
  model.className = "model-chip";
  model.textContent = `${settings.aspect_ratio || aspectRatioSelect.value} · ${settings.image_size || imageSizeSelect.value}`;
  head.append(avatar, role, model);
  bubble.appendChild(head);

  if (pending) {
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    bubble.appendChild(typing);
    bubble.appendChild(buildMessageMeta(createdAt));
    message.appendChild(bubble);
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
    const actions = document.createElement("figcaption");
    actions.className = "image-card-actions";
    actions.innerHTML = `
      <button class="image-action edit-image" type="button">Edit this</button>
      <a class="image-action download-image" download="generated-image.png">Download</a>
    `;
    actions.querySelector(".download-image").href = imageSrc;
    card.append(img, actions);
    bubble.appendChild(card);
  });

  if (!trimmed && images.length === 0) {
    const fallback = document.createElement("p");
    fallback.className = "message-text";
    fallback.textContent = "No content returned.";
    bubble.appendChild(fallback);
  }

  bubble.appendChild(buildMessageMeta(createdAt));
  message.appendChild(bubble);
  return message;
}

function appendUserBubble(prompt, sourceImage = null) {
  ensureNotEmpty();
  imageThread.appendChild(buildUserBubble(prompt, sourceImage));
  scrollToLatestImage();
}

function appendAssistantBubble(payload = {}) {
  ensureNotEmpty();
  const node = buildAssistantBubble(payload);
  imageThread.appendChild(node);
  scrollToLatestImage();
  return node;
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

function renderJob(job, { prepend = false } = {}) {
  const fragment = document.createDocumentFragment();
  fragment.appendChild(buildUserBubble(job.prompt, null, job.createdAt));
  fragment.appendChild(
    buildAssistantBubble({
      text: job.text || "",
      images: job.resultUrls || [],
      settings: job.settings || {},
      createdAt: job.createdAt,
    }),
  );
  ensureNotEmpty();
  if (prepend) imageThread.prepend(fragment);
  else imageThread.appendChild(fragment);
}

function renderConversations() {
  if (!state.conversations.length) {
    conversationList.innerHTML = '<p class="image-list-hint">No saved image chats yet.</p>';
    return;
  }
  conversationList.innerHTML = "";
  state.conversations.forEach((conversation) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `image-conversation-item${conversation.id === state.activeConversationId ? " active" : ""}`;
    button.dataset.conversationId = conversation.id;
    button.innerHTML = `
      <span>
        <span class="image-conversation-title"></span>
        <span class="image-conversation-time">${formatConversationTime(conversation.updatedAt)}</span>
      </span>
      <span class="image-conversation-menu" aria-hidden="true">›</span>
    `;
    button.querySelector(".image-conversation-title").textContent = conversation.title;
    conversationList.appendChild(button);
  });
}

function upsertConversation(conversation) {
  if (!conversation) return;
  state.conversations = state.conversations.filter((item) => item.id !== conversation.id);
  state.conversations.unshift(conversation);
  state.activeConversationId = conversation.id;
  chatTitle.textContent = conversation.title || "Image Studio";
  renderConversations();
}

async function loadConversations() {
  state.loadingConversations = true;
  try {
    const response = await apiFetch(API.conversations, { method: "GET" });
    const data = await parseApiResponse(response);
    if (!response.ok) throw new Error(data.error || "Failed to load chats");
    state.conversations = data.items || [];
    renderConversations();
  } catch (_error) {
    conversationList.innerHTML = '<p class="image-list-hint">Could not load chats.</p>';
  } finally {
    state.loadingConversations = false;
  }
}

async function loadConversationJobs(conversationId, { prepend = false } = {}) {
  if (!conversationId || state.loadingJobs) return;
  state.loadingJobs = true;
  const previousHeight = imageThread.scrollHeight;
  let loader = null;
  if (prepend) {
    loader = document.createElement("div");
    loader.className = "history-loader";
    loader.textContent = "Loading earlier…";
    imageThread.prepend(loader);
  }
  try {
    const cursor = prepend && state.oldestJobCursor ? `&before=${encodeURIComponent(state.oldestJobCursor)}` : "";
    const response = await apiFetch(`${API.conversationBase}/${conversationId}/jobs?limit=12${cursor}`, { method: "GET" });
    const data = await parseApiResponse(response);
    if (!response.ok) throw new Error(data.error || "Failed to load messages");
    loader?.remove();
    if (!prepend) imageThread.innerHTML = "";
    const items = data.items || [];
    if (!items.length && !prepend) resetThread();
    const renderItems = prepend ? [...items].reverse() : items;
    renderItems.forEach((job) => renderJob(job, { prepend }));
    state.hasMoreJobs = Boolean(data.hasMore);
    state.oldestJobCursor = items[0]?.createdAt || state.oldestJobCursor;
    if (prepend) imageThread.scrollTop = imageThread.scrollHeight - previousHeight;
    else scrollToLatestImage();
  } catch (_error) {
    loader?.remove();
    if (!prepend) {
      resetThread();
      setStatus("Could not load this image chat.");
    }
  } finally {
    state.loadingJobs = false;
  }
}

function startNewChat() {
  state.activeConversationId = null;
  chatTitle.textContent = "Image Studio";
  resetThread();
  setSelectedSource(null);
  renderConversations();
  promptInput.focus();
}

function selectConversation(conversationId) {
  const conversation = state.conversations.find((item) => item.id === conversationId);
  if (!conversation) return;
  state.activeConversationId = conversation.id;
  chatTitle.textContent = conversation.title || "Image Studio";
  renderConversations();
  resetThread();
  loadConversationJobs(conversation.id);
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
  if (selectedSourceImage && !selectedModelSupportsEdit()) {
    setStatus(`${selectedModelConfig()?.label || "This model"} does not support reference-image edits.`);
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
  appendUserBubble(prompt, requestSource);
  const pendingBubble = appendAssistantBubble({ pending: true, settings: requestSettings });
  setStatus(isEdit ? "Editing image..." : "Generating image...");
  try {
    const response = await apiFetch(isEdit ? "/api/image/edit" : "/api/image/generate", {
      method: "POST",
      body: JSON.stringify(
        isEdit
          ? { conversation_id: state.activeConversationId, prompt, input_image: selectedSourceImage, ...requestSettings }
          : { conversation_id: state.activeConversationId, prompt, ...requestSettings },
      ),
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
    appendAssistantBubble({ text: data.text || "", images, settings: data.settings || requestSettings });
    upsertConversation(data.conversation);

    promptInput.value = "";
    autosizeInput();
    setStatus(data.text ? "Response ready." : isEdit ? "Image edited." : "Image generated.");
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

function clearSelectedCard() {
  document.querySelectorAll(".image-card.selected").forEach((card) => card.classList.remove("selected"));
}

function setSelectedSource(src, sourceType = "selected") {
  selectedSourceImage = src || null;
  if (selectedSourceImage) {
    const supportsEdit = selectedModelSupportsEdit();
    generateButton.title = supportsEdit ? "Edit selected image" : "Selected model does not support reference edits";
    sourceStatus.textContent = supportsEdit
      ? sourceType === "upload" ? "Uploaded reference" : "Selected reference"
      : "Reference not supported";
    sourcePreviewImage.src = selectedSourceImage;
    sourcePreview.classList.remove("hidden");
  } else {
    generateButton.title = "Generate image";
    sourceStatus.textContent = "New image";
    sourcePreviewImage.removeAttribute("src");
    sourcePreview.classList.add("hidden");
    clearSelectedCard();
  }
  updateGenerateButton();
}

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

function bindPromptStarters() {
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      promptInput.value = button.dataset.prompt || "";
      autosizeInput();
      promptInput.focus();
    });
  });
}

newChatButton.addEventListener("click", startNewChat);
conversationList.addEventListener("click", (event) => {
  const item = event.target.closest(".image-conversation-item");
  if (item) selectConversation(item.dataset.conversationId);
});

pickSourceButton.addEventListener("click", () => sourceUpload.click());
clearSourceButton.addEventListener("click", () => setSelectedSource(null));
sourceUpload.addEventListener("change", () => {
  const file = sourceUpload.files && sourceUpload.files[0];
  loadSourceFile(file);
  sourceUpload.value = "";
});

imageThread.addEventListener("scroll", () => {
  if (imageThread.scrollTop < 80 && state.activeConversationId && state.hasMoreJobs && !state.loadingJobs) {
    loadConversationJobs(state.activeConversationId, { prepend: true });
  }
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
  if (!(target instanceof HTMLImageElement) || !target.classList.contains("editable-image")) return;
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
resetThread();
loadConversations();
