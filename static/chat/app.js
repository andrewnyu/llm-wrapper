const state = {
  conversations: [],
  activeConversationId: null,
  messages: [],
  streaming: false,
  activeRequestId: null,
  autoScroll: true,
  lastFailedContent: "",
  sidebarOpen: false,
  typingMessageId: null,
  selectedProvider: "",
  selectedModel: "",
  selectedModelLabel: "",
};

const elements = {
  app: document.getElementById("chat-app"),
  sidebar: document.getElementById("chat-sidebar"),
  sidebarOverlay: document.getElementById("sidebar-overlay"),
  openSidebarBtn: document.getElementById("open-sidebar-btn"),
  closeSidebarBtn: document.getElementById("close-sidebar-btn"),
  conversationList: document.getElementById("conversation-list"),
  messageList: document.getElementById("message-list"),
  threadEmpty: document.getElementById("thread-empty"),
  threadTitle: document.getElementById("thread-title"),
  threadSubtitle: document.getElementById("thread-subtitle"),
  modelSwitcher: document.getElementById("model-switcher"),
  modelHint: document.getElementById("model-hint"),
  newChatBtn: document.getElementById("new-chat-btn"),
  sendBtn: document.getElementById("send-btn"),
  stopBtn: document.getElementById("stop-btn"),
  input: document.getElementById("composer-input"),
  jumpLatestBtn: document.getElementById("jump-latest-btn"),
};

const API = {
  conversations: "/api/conversations",
  cancel: "/api/generate/cancel",
};

function getCsrfToken() {
  const fromData = elements.app?.dataset?.csrfToken;
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

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatClockTime(isoTime) {
  if (!isoTime) return "";
  const date = new Date(isoTime);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatRelativeTime(isoTime) {
  if (!isoTime) return "";
  const then = new Date(isoTime).getTime();
  const now = Date.now();
  const minutes = Math.max(1, Math.floor((now - then) / 60000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function modelLabelForId(modelId) {
  if (!modelId) return "";
  const option = Array.from(elements.modelSwitcher?.options || []).find(
    (item) => item.dataset.model === modelId,
  );
  return option?.dataset.label || modelId;
}

function renderInlineMarkdown(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    )
    .replace(/\n/g, "<br>");
}

function renderMarkdown(text) {
  const blocks = [];
  const pattern = /```([\w-]+)?\n?([\s\S]*?)```/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      blocks.push({ type: "text", value: text.slice(cursor, match.index) });
    }
    blocks.push({ type: "code", value: match[2] || "" });
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) blocks.push({ type: "text", value: text.slice(cursor) });
  if (!blocks.length) blocks.push({ type: "text", value: text });

  return blocks
    .map((block) => {
      if (block.type === "code") {
        return `
          <pre class="code-block">
            <button class="copy-code-btn" type="button" data-code="${encodeURIComponent(block.value)}">Copy</button>
            <code>${escapeHtml(block.value)}</code>
          </pre>
        `;
      }
      return `<div class="markdown-block">${renderInlineMarkdown(block.value)}</div>`;
    })
    .join("");
}

function getActiveConversation() {
  return state.conversations.find((item) => item.id === state.activeConversationId) || null;
}

function setSidebarOpen(open) {
  state.sidebarOpen = open;
  elements.sidebar.classList.toggle("open", open);
  elements.sidebarOverlay.classList.toggle("hidden", !open);
}

function updateThreadTitle() {
  const active = getActiveConversation();
  elements.threadTitle.textContent = active?.title || "New chat";
}

function selectModel(value, persist = true) {
  const option = Array.from(elements.modelSwitcher?.options || []).find(
    (item) => item.value === value && !item.disabled,
  ) || Array.from(elements.modelSwitcher?.options || []).find((item) => !item.disabled);
  if (!option) {
    state.selectedProvider = "";
    state.selectedModel = "";
    state.selectedModelLabel = "No model configured";
    elements.modelSwitcher.disabled = true;
    elements.sendBtn.disabled = true;
    elements.modelHint.textContent = "Ask an admin to configure a provider API key";
    return;
  }
  elements.modelSwitcher.value = option.value;
  state.selectedProvider = option.dataset.provider || "";
  state.selectedModel = option.dataset.model || "";
  state.selectedModelLabel = option.dataset.label || option.textContent.trim();
  elements.threadSubtitle.textContent = state.selectedModelLabel;
  elements.modelHint.textContent = `${state.selectedModelLabel} will answer your next message`;
  if (persist) localStorage.setItem("chat-model", option.value);
}

function setStreaming(isStreaming) {
  state.streaming = isStreaming;
  elements.sendBtn.disabled = isStreaming || !state.selectedModel;
  elements.stopBtn.classList.toggle("hidden", !isStreaming);
}

function nearBottom() {
  const node = elements.messageList;
  return node.scrollHeight - node.scrollTop - node.clientHeight < 120;
}

function scrollToBottom(force = false) {
  if (!force && !state.autoScroll) return;
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
  elements.jumpLatestBtn.classList.add("hidden");
}

function onMessageScroll() {
  state.autoScroll = nearBottom();
  elements.jumpLatestBtn.classList.toggle("hidden", state.autoScroll);
}

function addInlineError(text, retryable = false) {
  state.messages.push({
    id: `error-${Date.now()}`,
    role: "system",
    content: text,
    createdAt: new Date().toISOString(),
    isError: true,
    retryable,
  });
  renderMessages();
}

function renderConversations() {
  const activeId = state.activeConversationId;
  if (!state.conversations.length) {
    elements.conversationList.innerHTML = `<div class="muted">No conversations yet</div>`;
    return;
  }
  elements.conversationList.innerHTML = state.conversations
    .map((conversation) => {
      const active = conversation.id === activeId ? "active" : "";
      return `
        <div class="conversation-item ${active}" data-id="${conversation.id}">
          <button class="conversation-open" type="button" data-id="${conversation.id}">
            <div class="conversation-title">${escapeHtml(conversation.title)}</div>
            <div class="conversation-time">${formatRelativeTime(conversation.updatedAt)}</div>
          </button>
          <button class="conversation-more" type="button" data-id="${conversation.id}" title="Rename">✎</button>
          <button class="conversation-delete" type="button" data-id="${conversation.id}" title="Delete">🗑</button>
        </div>
      `;
    })
    .join("");
}

function renderTypingIndicator() {
  return `
    <div class="typing-indicator" aria-label="Typing">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
}

function renderMessages() {
  elements.threadEmpty.classList.toggle("hidden", state.messages.length > 0);
  elements.messageList.innerHTML = state.messages
    .map((message) => {
      const classes = [
        "message-item",
        message.role,
        message.isError ? "error" : "",
      ]
        .filter(Boolean)
        .join(" ");

      const isAssistant = message.role === "assistant";
      const isTyping = Boolean(message.typing);
      const body = isTyping
        ? renderTypingIndicator()
        : isAssistant
          ? renderMarkdown(message.content || "")
          : `<div class="markdown-block">${escapeHtml(message.content || "")}</div>`;

      const copyButton = message.content
        ? `<button class="message-copy" type="button" data-copy="${encodeURIComponent(message.content)}">Copy</button>`
        : "";

      const retry = message.retryable ? '<button class="retry-btn" type="button">Retry</button>' : "";
      const metaParts = [];
      if (isAssistant && message.model) metaParts.push(modelLabelForId(message.model));
      metaParts.push(formatClockTime(message.createdAt));
      return `
        <article class="${classes}" data-id="${message.id || ""}">
          ${copyButton}
          ${body}
          <div class="message-meta">${metaParts.filter(Boolean).join(" · ")}</div>
          ${retry}
        </article>
      `;
    })
    .join("");

  elements.jumpLatestBtn.classList.toggle("hidden", state.autoScroll);
  scrollToBottom();
}

function autosizeTextarea() {
  const node = elements.input;
  node.style.height = "auto";
  node.style.height = `${Math.min(node.scrollHeight, 180)}px`;
}

async function listConversations() {
  const response = await apiFetch(API.conversations);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Failed to load conversations");
  state.conversations = data.items || [];
  if (!state.activeConversationId && state.conversations.length) {
    state.activeConversationId = state.conversations[0].id;
  }
  renderConversations();
  updateThreadTitle();
}

async function loadMessages(conversationId) {
  const response = await apiFetch(`${API.conversations}/${conversationId}/messages`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Failed to load messages");
  state.messages = data.items || [];
  renderMessages();
  scrollToBottom(true);
}

async function createConversation() {
  const response = await apiFetch(API.conversations, {
    method: "POST",
    body: JSON.stringify({ title: "New chat" }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Failed to create conversation");
  state.conversations.unshift(data);
  state.activeConversationId = data.id;
  state.messages = [];
  renderConversations();
  renderMessages();
  updateThreadTitle();
}

async function renameConversation(conversationId) {
  const current = state.conversations.find((item) => item.id === conversationId);
  if (!current) return;
  const nextTitle = window.prompt("Rename chat", current.title);
  if (!nextTitle || !nextTitle.trim()) return;

  const response = await apiFetch(`${API.conversations}/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title: nextTitle.trim() }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Failed to rename");
  state.conversations = state.conversations.map((item) => (item.id === conversationId ? data : item));
  renderConversations();
  updateThreadTitle();
}

async function deleteConversation(conversationId) {
  if (!window.confirm("Delete this conversation?")) return;
  const response = await apiFetch(`${API.conversations}/${conversationId}`, { method: "DELETE" });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || "Failed to delete conversation");
  }
  state.conversations = state.conversations.filter((item) => item.id !== conversationId);
  if (state.activeConversationId === conversationId) {
    state.activeConversationId = state.conversations[0]?.id || null;
    state.messages = [];
    if (state.activeConversationId) await loadMessages(state.activeConversationId);
    else renderMessages();
  }
  renderConversations();
  updateThreadTitle();
}

function addTypingPlaceholder() {
  const id = `typing-${Date.now()}`;
  state.typingMessageId = id;
  state.messages.push({
    id,
    role: "assistant",
    content: "",
    createdAt: new Date().toISOString(),
    typing: true,
  });
}

function replaceTypingWithAssistant(messageId, initialChunk = "") {
  const idx = state.messages.findIndex((item) => item.id === state.typingMessageId);
  if (idx >= 0) {
    state.messages[idx] = {
      id: messageId,
      role: "assistant",
      content: initialChunk,
      createdAt: new Date().toISOString(),
      streaming: true,
      model: state.selectedModel,
    };
  } else {
    state.messages.push({
      id: messageId,
      role: "assistant",
      content: initialChunk,
      createdAt: new Date().toISOString(),
      streaming: true,
      model: state.selectedModel,
    });
  }
  state.typingMessageId = null;
}

function upsertStreamingAssistant(messageId, chunk) {
  const index = state.messages.findIndex((item) => item.id === messageId);
  if (index === -1) {
    replaceTypingWithAssistant(messageId, chunk);
  } else {
    state.messages[index].content += chunk;
    state.messages[index].streaming = true;
  }
  renderMessages();
}

function finishStreamingAssistant(messageId, fullText) {
  const index = state.messages.findIndex((item) => item.id === messageId);
  if (index === -1) {
    state.messages.push({
      id: messageId,
      role: "assistant",
      content: fullText || "",
      createdAt: new Date().toISOString(),
    });
  } else {
    state.messages[index].content = fullText ?? state.messages[index].content;
    state.messages[index].streaming = false;
  }
  state.typingMessageId = null;
  renderMessages();
}

async function cancelStreaming() {
  if (!state.activeRequestId) return;
  await apiFetch(API.cancel, {
    method: "POST",
    body: JSON.stringify({ requestId: state.activeRequestId }),
  });
}

function parseSseChunk(buffer, onEvent) {
  const parts = buffer.split("\n\n");
  for (let i = 0; i < parts.length - 1; i += 1) {
    const raw = parts[i].trim();
    if (!raw) continue;
    let eventName = "message";
    let data = "";
    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    try {
      onEvent(eventName, data ? JSON.parse(data) : {});
    } catch (error) {
      console.error("SSE parse error", error);
    }
  }
  return parts[parts.length - 1] || "";
}

async function sendMessage() {
  const content = elements.input.value.trim();
  const conversation = getActiveConversation();
  if (!content || !conversation || state.streaming) return;

  state.lastFailedContent = content;
  state.messages.push({
    id: `user-${Date.now()}`,
    role: "user",
    content,
    createdAt: new Date().toISOString(),
  });
  addTypingPlaceholder();
  elements.input.value = "";
  autosizeTextarea();
  state.autoScroll = true;
  renderMessages();
  setStreaming(true);

  let assistantMessageId = `assistant-${Date.now()}`;
  try {
    const response = await apiFetch(`${API.conversations}/${conversation.id}/messages`, {
      method: "POST",
      body: JSON.stringify({
        content,
        provider: state.selectedProvider,
        model: state.selectedModel,
      }),
    });
    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "Failed to stream response");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";
    let sawDelta = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      pending = parseSseChunk(pending, (eventName, data) => {
        if (eventName === "meta") {
          state.activeRequestId = data.requestId;
          assistantMessageId = data.messageId || assistantMessageId;
        } else if (eventName === "delta") {
          if (!sawDelta) {
            replaceTypingWithAssistant(assistantMessageId, "");
            sawDelta = true;
          }
          upsertStreamingAssistant(assistantMessageId, data.text || "");
        } else if (eventName === "done") {
          finishStreamingAssistant(assistantMessageId, data.fullText || "");
          state.activeRequestId = null;
        } else if (eventName === "error") {
          state.activeRequestId = null;
          addInlineError(data.message || "Generation failed", true);
        }
      });
    }
    await listConversations();
  } catch (error) {
    addInlineError(error.message || "Network error", true);
  } finally {
    state.activeRequestId = null;
    setStreaming(false);
  }
}

function bindEvents() {
  elements.newChatBtn.addEventListener("click", async () => {
    try {
      await createConversation();
      if (window.innerWidth <= 960) setSidebarOpen(false);
    } catch (error) {
      addInlineError(error.message || "Failed to create conversation");
    }
  });

  elements.sendBtn.addEventListener("click", sendMessage);
  elements.modelSwitcher?.addEventListener("change", () => selectModel(elements.modelSwitcher.value));
  elements.stopBtn.addEventListener("click", cancelStreaming);
  elements.jumpLatestBtn.addEventListener("click", () => {
    state.autoScroll = true;
    scrollToBottom(true);
  });

  elements.openSidebarBtn?.addEventListener("click", () => setSidebarOpen(true));
  elements.closeSidebarBtn?.addEventListener("click", () => setSidebarOpen(false));
  elements.sidebarOverlay?.addEventListener("click", () => setSidebarOpen(false));

  elements.messageList.addEventListener("scroll", onMessageScroll);
  elements.messageList.addEventListener("click", async (event) => {
    const copyCodeBtn = event.target.closest(".copy-code-btn");
    if (copyCodeBtn) {
      const value = decodeURIComponent(copyCodeBtn.dataset.code || "");
      await navigator.clipboard.writeText(value);
      copyCodeBtn.textContent = "Copied";
      setTimeout(() => {
        copyCodeBtn.textContent = "Copy";
      }, 1000);
      return;
    }

    const copyMessageBtn = event.target.closest(".message-copy");
    if (copyMessageBtn) {
      const value = decodeURIComponent(copyMessageBtn.dataset.copy || "");
      await navigator.clipboard.writeText(value);
      copyMessageBtn.textContent = "Copied";
      setTimeout(() => {
        copyMessageBtn.textContent = "Copy";
      }, 1000);
      return;
    }

    const retryBtn = event.target.closest(".retry-btn");
    if (retryBtn) {
      elements.input.value = state.lastFailedContent;
      autosizeTextarea();
      await sendMessage();
    }
  });

  elements.conversationList.addEventListener("click", async (event) => {
    const openBtn = event.target.closest(".conversation-open");
    if (openBtn) {
      state.activeConversationId = openBtn.dataset.id;
      renderConversations();
      updateThreadTitle();
      try {
        await loadMessages(state.activeConversationId);
        if (window.innerWidth <= 960) setSidebarOpen(false);
      } catch (error) {
        addInlineError(error.message || "Failed to load conversation");
      }
      return;
    }

    const renameBtn = event.target.closest(".conversation-more");
    if (renameBtn) {
      try {
        await renameConversation(renameBtn.dataset.id);
      } catch (error) {
        addInlineError(error.message || "Failed to rename conversation");
      }
      return;
    }

    const deleteBtn = event.target.closest(".conversation-delete");
    if (deleteBtn) {
      try {
        await deleteConversation(deleteBtn.dataset.id);
      } catch (error) {
        addInlineError(error.message || "Failed to delete conversation");
      }
    }
  });

  elements.input.addEventListener("input", autosizeTextarea);
  elements.input.addEventListener("keydown", async (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await sendMessage();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 960) setSidebarOpen(false);
  });
}

async function bootstrap() {
  bindEvents();
  autosizeTextarea();
  selectModel(localStorage.getItem("chat-model") || elements.modelSwitcher?.value || "", false);

  try {
    await listConversations();
    if (!state.activeConversationId) await createConversation();
    else await loadMessages(state.activeConversationId);
  } catch (error) {
    addInlineError(error.message || "Failed to load chat");
  }
}

bootstrap();
