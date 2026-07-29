const KIND = "feedback";
const API = {
  conversations: `/api/image/conversations?kind=${KIND}`,
  conversationBase: "/api/image/conversations",
};

const app = document.getElementById("feedback-app");
const promptInput = document.getElementById("feedback-prompt");
const sendButton = document.getElementById("feedback-send");
const thread = document.getElementById("feedback-thread");
const status = document.getElementById("feedback-status");
const pickSourceButton = document.getElementById("feedback-pick-source");
const clearSourceButton = document.getElementById("feedback-clear-source");
const sourceStatus = document.getElementById("feedback-source-status");
const sourceUpload = document.getElementById("feedback-source-upload");
const presetButtons = document.querySelectorAll(".preset-btn");
const chatTitle = document.getElementById("feedback-chat-title");
const newChatButton = document.getElementById("new-feedback-chat");
const conversationList = document.getElementById("feedback-conversation-list");

const state = {
  conversations: [],
  activeConversationId: null,
  hasMoreJobs: false,
  oldestJobCursor: null,
  loadingJobs: false,
};

let selectedSourceImage = null;
let isSending = false;

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

function emptyMarkup() {
  return `
    <div id="feedback-empty" class="image-empty">
      <div class="empty-orbit" aria-hidden="true">↗</div>
      <h2>Review an image</h2>
      <p>Upload or paste an image, then ask for text checks, comments, or design feedback.</p>
    </div>
  `;
}

function resetThread() {
  thread.innerHTML = emptyMarkup();
  state.hasMoreJobs = false;
  state.oldestJobCursor = null;
}

function ensureNotEmpty() {
  document.getElementById("feedback-empty")?.remove();
}

function scrollToLatest() {
  thread.scrollTop = thread.scrollHeight;
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
  const text = document.createElement("p");
  text.className = "message-text user-text";
  text.textContent = prompt;
  bubble.append(role, text);

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
  const role = document.createElement("span");
  role.className = "message-role";
  role.textContent = settings.model_label || "Gemini 2.5 Flash Image";
  const model = document.createElement("span");
  model.className = "model-chip";
  model.textContent = "Image feedback";
  head.append(role, model);
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

  bubble.appendChild(buildMessageMeta(createdAt));
  message.appendChild(bubble);
  return message;
}

function appendUserBubble(prompt, sourceImage) {
  ensureNotEmpty();
  thread.appendChild(buildUserBubble(prompt, sourceImage));
  scrollToLatest();
}

function appendAssistantBubble(payload = {}) {
  ensureNotEmpty();
  const node = buildAssistantBubble(payload);
  thread.appendChild(node);
  scrollToLatest();
  return node;
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
  if (prepend) thread.prepend(fragment);
  else thread.appendChild(fragment);
}

function renderConversations() {
  if (!state.conversations.length) {
    conversationList.innerHTML = '<p class="image-list-hint">No saved feedback chats yet.</p>';
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
  chatTitle.textContent = conversation.title || "Image Feedback";
  renderConversations();
}

async function loadConversations() {
  try {
    const response = await apiFetch(API.conversations, { method: "GET" });
    const data = await parseApiResponse(response);
    if (!response.ok) throw new Error(data.error || "Failed to load chats");
    state.conversations = data.items || [];
    renderConversations();
  } catch (_error) {
    conversationList.innerHTML = '<p class="image-list-hint">Could not load chats.</p>';
  }
}

async function loadConversationJobs(conversationId, { prepend = false } = {}) {
  if (!conversationId || state.loadingJobs) return;
  state.loadingJobs = true;
  const previousHeight = thread.scrollHeight;
  let loader = null;
  if (prepend) {
    loader = document.createElement("div");
    loader.className = "history-loader";
    loader.textContent = "Loading earlier…";
    thread.prepend(loader);
  }
  try {
    const cursor = prepend && state.oldestJobCursor ? `&before=${encodeURIComponent(state.oldestJobCursor)}` : "";
    const response = await apiFetch(`${API.conversationBase}/${conversationId}/jobs?limit=12${cursor}`, { method: "GET" });
    const data = await parseApiResponse(response);
    if (!response.ok) throw new Error(data.error || "Failed to load messages");
    loader?.remove();
    if (!prepend) thread.innerHTML = "";
    const items = data.items || [];
    if (!items.length && !prepend) resetThread();
    const renderItems = prepend ? [...items].reverse() : items;
    renderItems.forEach((job) => renderJob(job, { prepend }));
    state.hasMoreJobs = Boolean(data.hasMore);
    state.oldestJobCursor = items[0]?.createdAt || state.oldestJobCursor;
    if (prepend) thread.scrollTop = thread.scrollHeight - previousHeight;
    else scrollToLatest();
  } catch (_error) {
    loader?.remove();
    if (!prepend) {
      resetThread();
      setStatus("Could not load this feedback chat.");
    }
  } finally {
    state.loadingJobs = false;
  }
}

function startNewChat() {
  state.activeConversationId = null;
  chatTitle.textContent = "Image Feedback";
  resetThread();
  setSelectedSource(null);
  renderConversations();
  promptInput.focus();
}

function selectConversation(conversationId) {
  const conversation = state.conversations.find((item) => item.id === conversationId);
  if (!conversation) return;
  state.activeConversationId = conversation.id;
  chatTitle.textContent = conversation.title || "Image Feedback";
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

async function runFeedbackRequest() {
  if (isSending) return;
  if (!selectedSourceImage) {
    setStatus("Upload an image first.");
    return;
  }

  const prompt = promptInput.value.trim();
  const displayPrompt = prompt || "Analyze this image: description, spelling issues, and comments.";

  isSending = true;
  sendButton.disabled = true;
  appendUserBubble(displayPrompt, selectedSourceImage);
  const pendingBubble = appendAssistantBubble({ pending: true });
  setStatus("Analyzing image...");

  try {
    const response = await apiFetch("/api/image/feedback", {
      method: "POST",
      body: JSON.stringify({ conversation_id: state.activeConversationId, prompt, input_image: selectedSourceImage }),
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
    const images = (data.images || []).map((image) => image.url || image.base64).filter(Boolean);
    appendAssistantBubble({ text: data.text || "", images, settings: data.job?.settings || {} });
    upsertConversation(data.conversation);

    promptInput.value = "";
    autosizeInput();
    setStatus("Feedback ready.");
    window.setTimeout(() => setStatus(""), 1400);
  } catch (_error) {
    pendingBubble.remove();
    addErrorBubble("Network error. Please retry.");
    setStatus("Network error. Please retry.");
  } finally {
    isSending = false;
    sendButton.disabled = false;
  }
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

function loadSourceFile(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setStatus("Please choose an image file.");
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
    setStatus("Image uploaded. Ask for feedback.");
    window.setTimeout(() => setStatus(""), 1400);
  };
  reader.onerror = () => setStatus("Could not read selected image");
  reader.readAsDataURL(file);
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

thread.addEventListener("scroll", () => {
  if (thread.scrollTop < 80 && state.activeConversationId && state.hasMoreJobs && !state.loadingJobs) {
    loadConversationJobs(state.activeConversationId, { prepend: true });
  }
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

document.addEventListener("paste", (event) => {
  const imageItem = Array.from(event.clipboardData?.items || []).find((item) => item.type.startsWith("image/"));
  if (imageItem) loadSourceFile(imageItem.getAsFile());
});

autosizeInput();
resetThread();
loadConversations();
