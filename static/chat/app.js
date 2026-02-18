const state = {
  conversations: [],
  activeConversationId: null,
  messages: [],
  streaming: false,
  activeRequestId: null,
  autoScroll: true,
  lastFailedContent: "",
};

const elements = {
  app: document.getElementById("chat-app"),
  conversationList: document.getElementById("conversation-list"),
  messageList: document.getElementById("message-list"),
  threadEmpty: document.getElementById("thread-empty"),
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
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
      ...(options.headers || {}),
    },
    ...options,
  });
  return response;
}

function formatRelativeTime(isoTime) {
  const then = new Date(isoTime).getTime();
  const now = Date.now();
  const diffMinutes = Math.max(1, Math.floor((now - then) / 60000));
  if (diffMinutes < 60) return `${diffMinutes}m`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d`;
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
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
    blocks.push({
      type: "code",
      language: match[1] || "",
      value: match[2] || "",
    });
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) {
    blocks.push({ type: "text", value: text.slice(cursor) });
  }
  if (!blocks.length) {
    blocks.push({ type: "text", value: text });
  }

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

function setStreaming(isStreaming) {
  state.streaming = isStreaming;
  elements.sendBtn.disabled = isStreaming;
  elements.input.disabled = isStreaming;
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
  if (state.autoScroll) {
    elements.jumpLatestBtn.classList.add("hidden");
  }
}

function addInlineError(text, retryable = false) {
  state.messages.push({
    id: `error-${Date.now()}`,
    role: "system",
    content: text,
    isError: true,
    retryable,
  });
  renderMessages();
}

function renderConversations() {
  const activeId = state.activeConversationId;
  if (!state.conversations.length) {
    elements.conversationList.innerHTML = `<div class="muted">No chats yet</div>`;
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
          <button class="conversation-more" type="button" data-id="${conversation.id}" title="Rename">Rename</button>
          <button class="conversation-delete" type="button" data-id="${conversation.id}" title="Delete">Delete</button>
        </div>
      `;
    })
    .join("");
}

function renderMessages() {
  elements.threadEmpty.classList.toggle("hidden", state.messages.length > 0);
  elements.messageList.innerHTML = state.messages
    .map((message) => {
      const isAssistant = message.role === "assistant";
      const isUser = message.role === "user";
      const isSystem = message.role === "system";
      const classes = [
        "message-item",
        isAssistant ? "assistant" : "",
        isUser ? "user" : "",
        isSystem ? "system" : "",
        message.isError ? "error" : "",
      ]
        .filter(Boolean)
        .join(" ");

      const body = isAssistant ? renderMarkdown(message.content) : `<div class="markdown-block">${escapeHtml(message.content || "")}</div>`;
      const cursor = message.streaming ? '<span class="stream-cursor"></span>' : "";
      const retry = message.retryable ? '<button class="retry-btn" type="button">Retry</button>' : "";
      return `<div class="${classes}" data-id="${message.id || ""}">${body}${cursor}${retry}</div>`;
    })
    .join("");

  if (!state.autoScroll) {
    elements.jumpLatestBtn.classList.remove("hidden");
  }
  scrollToBottom();
}

function autosizeTextarea() {
  const node = elements.input;
  node.style.height = "auto";
  node.style.height = `${Math.min(node.scrollHeight, 200)}px`;
}

async function listConversations() {
  const response = await apiFetch(API.conversations);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Failed to load conversations");
  }
  state.conversations = data.items || [];
  if (!state.activeConversationId && state.conversations.length) {
    state.activeConversationId = state.conversations[0].id;
  }
  renderConversations();
}

async function loadMessages(conversationId) {
  const response = await apiFetch(`${API.conversations}/${conversationId}/messages`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Failed to load messages");
  }
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
  if (!response.ok) {
    throw new Error(data.error || "Failed to create conversation");
  }
  state.conversations.unshift(data);
  state.activeConversationId = data.id;
  state.messages = [];
  renderConversations();
  renderMessages();
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
  if (!response.ok) {
    throw new Error(data.error || "Failed to rename conversation");
  }
  state.conversations = state.conversations.map((item) => (item.id === conversationId ? data : item));
  renderConversations();
}

async function deleteConversation(conversationId) {
  const ok = window.confirm("Delete this conversation?");
  if (!ok) return;
  const response = await apiFetch(`${API.conversations}/${conversationId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || "Failed to delete conversation");
  }
  state.conversations = state.conversations.filter((item) => item.id !== conversationId);
  if (state.activeConversationId === conversationId) {
    state.activeConversationId = state.conversations[0]?.id || null;
    state.messages = [];
    if (state.activeConversationId) {
      await loadMessages(state.activeConversationId);
    } else {
      renderMessages();
    }
  }
  renderConversations();
}

function upsertStreamingAssistant(messageId, chunk) {
  const index = state.messages.findIndex((item) => item.id === messageId);
  if (index === -1) {
    state.messages.push({
      id: messageId,
      role: "assistant",
      content: chunk,
      streaming: true,
    });
  } else {
    state.messages[index].content += chunk;
    state.messages[index].streaming = true;
  }
  renderMessages();
}

function finishStreamingAssistant(messageId, fullText) {
  const index = state.messages.findIndex((item) => item.id === messageId);
  if (index === -1) {
    state.messages.push({ id: messageId, role: "assistant", content: fullText || "", streaming: false });
  } else {
    state.messages[index].content = fullText ?? state.messages[index].content;
    state.messages[index].streaming = false;
  }
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
    } catch (err) {
      console.error("Failed parsing event payload", err);
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
  });
  elements.input.value = "";
  autosizeTextarea();
  state.autoScroll = true;
  renderMessages();
  setStreaming(true);

  let assistantMessageId = `assistant-${Date.now()}`;
  try {
    const response = await apiFetch(`${API.conversations}/${conversation.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "Failed to stream response");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      pending = parseSseChunk(pending, (eventName, data) => {
        if (eventName === "meta") {
          state.activeRequestId = data.requestId;
          assistantMessageId = data.messageId || assistantMessageId;
        } else if (eventName === "delta") {
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
    } catch (error) {
      addInlineError(error.message || "Failed to create conversation");
    }
  });

  elements.sendBtn.addEventListener("click", sendMessage);
  elements.stopBtn.addEventListener("click", cancelStreaming);
  elements.jumpLatestBtn.addEventListener("click", () => {
    state.autoScroll = true;
    scrollToBottom(true);
  });

  elements.messageList.addEventListener("scroll", onMessageScroll);
  elements.messageList.addEventListener("click", async (event) => {
    const copyBtn = event.target.closest(".copy-code-btn");
    if (copyBtn) {
      const value = decodeURIComponent(copyBtn.dataset.code || "");
      await navigator.clipboard.writeText(value);
      copyBtn.textContent = "Copied";
      window.setTimeout(() => {
        copyBtn.textContent = "Copy";
      }, 1000);
      return;
    }
    const retry = event.target.closest(".retry-btn");
    if (retry) {
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
      try {
        await loadMessages(state.activeConversationId);
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
}

async function bootstrap() {
  bindEvents();
  autosizeTextarea();
  try {
    await listConversations();
    if (!state.activeConversationId) {
      await createConversation();
    } else {
      await loadMessages(state.activeConversationId);
    }
  } catch (error) {
    addInlineError(error.message || "Failed to load chat");
  }
}

bootstrap();
