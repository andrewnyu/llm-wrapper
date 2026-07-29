const state = {
  conversations: [],
  activeConversationId: null,
  messages: [],
  streaming: false,
  activeRequestId: null,
  autoScroll: true,
  lastFailedContent: "",
  lastFailedMessageIds: [],
  sidebarOpen: false,
  typingMessageId: null,
  selectedProvider: "",
  selectedModel: "",
  selectedModelLabel: "",
  streamingConversationId: null,
  activeRequestController: null,
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
  modelPickerBtn: document.getElementById("model-picker-btn"),
  modelPickerLabel: document.getElementById("model-picker-label"),
  modelPickerMenu: document.getElementById("model-picker-menu"),
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

const DEFAULT_HINT = "Enter to send · Shift+Enter for a new line";

function updateSendButton() {
  elements.sendBtn.disabled =
    state.streaming ||
    !state.selectedModel ||
    !elements.input.value.trim();
}

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
  const { headers: optionHeaders = {}, ...fetchOptions } = options;
  return fetch(url, {
    credentials: "same-origin",
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
      ...optionHeaders,
    },
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

function providerLabel(provider) {
  return (provider || "provider")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function modelOptions() {
  return Array.from(elements.modelSwitcher?.options || []);
}

function setModelPickerOpen(isOpen) {
  if (!elements.modelPickerBtn || !elements.modelPickerMenu) return;
  elements.modelPickerMenu.classList.toggle("hidden", !isOpen);
  elements.modelPickerBtn.setAttribute("aria-expanded", String(isOpen));
}

function syncModelPickerSelection() {
  if (!elements.modelPickerLabel) return;
  elements.modelPickerLabel.textContent = state.selectedModelLabel || "Select model";
  elements.modelPickerBtn.disabled = !state.selectedModel;
  elements.modelPickerMenu?.querySelectorAll(".model-picker-option").forEach((button) => {
    const selected = button.dataset.value === elements.modelSwitcher?.value;
    button.setAttribute("aria-selected", String(selected));
    const check = button.querySelector(".model-picker-check");
    if (check) check.innerHTML = selected ? "✓" : "";
  });
}

function renderModelPicker() {
  if (!elements.modelPickerMenu) return;
  const groups = modelOptions().reduce((acc, option) => {
    const provider = option.dataset.provider || "other";
    if (!acc.has(provider)) acc.set(provider, []);
    acc.get(provider).push(option);
    return acc;
  }, new Map());

  elements.modelPickerMenu.innerHTML = Array.from(groups.entries())
    .map(([provider, options]) => {
      const buttons = options
        .map((option) => {
          const unavailable = option.disabled ? "Unavailable" : providerLabel(option.dataset.provider);
          return `
            <button
              class="model-picker-option"
              type="button"
              role="option"
              data-value="${escapeHtml(option.value)}"
              aria-selected="false"
              ${option.disabled ? "disabled" : ""}
            >
              <span class="model-picker-name">${escapeHtml(option.dataset.label || option.textContent.trim())}</span>
              <span class="model-picker-check" aria-hidden="true"></span>
              <span class="model-picker-provider">${escapeHtml(unavailable)}</span>
            </button>
          `;
        })
        .join("");
      return `<div class="model-picker-title">${escapeHtml(providerLabel(provider))}</div>${buttons}`;
    })
    .join("");
}

/* --------------------------------------------------------------------------
   Markdown rendering (block-level, escaped-first so it is XSS-safe)
   -------------------------------------------------------------------------- */

function renderInline(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/~~([^~]+)~~/g, "<del>$1</del>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    );
}

function renderCodeBlock(language, code) {
  const label = language ? escapeHtml(language) : "code";
  return `
    <div class="code-block">
      <div class="code-block-head">
        <span>${label}</span>
        <button class="copy-code-btn" type="button" data-code="${encodeURIComponent(code)}">Copy</button>
      </div>
      <pre><code>${escapeHtml(code)}</code></pre>
    </div>
  `;
}

function isTableSeparator(line) {
  return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(line);
}

function splitTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => renderInline(cell.trim()));
}

function renderTextBlocks(text) {
  const lines = text.split("\n");
  const html = [];
  let paragraph = [];
  let listStack = []; // {type: "ul"|"ol", indent}

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${paragraph.map(renderInline).join("<br>")}</p>`);
    paragraph = [];
  };

  const closeListsTo = (depth) => {
    while (listStack.length > depth) {
      html.push(`</${listStack.pop().type}>`);
    }
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();

    // Table: header row followed by separator row
    if (trimmed.startsWith("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      flushParagraph();
      closeListsTo(0);
      const headers = splitTableRow(trimmed);
      let j = i + 2;
      const rows = [];
      while (j < lines.length && lines[j].trim().startsWith("|")) {
        rows.push(splitTableRow(lines[j]));
        j += 1;
      }
      html.push(
        `<div class="markdown-table-wrap"><table><thead><tr>${headers
          .map((cell) => `<th>${cell}</th>`)
          .join("")}</tr></thead><tbody>${rows
          .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
          .join("")}</tbody></table></div>`,
      );
      i = j - 1;
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      closeListsTo(0);
      const level = headingMatch[1].length;
      html.push(`<h${level}>${renderInline(headingMatch[2])}</h${level}>`);
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushParagraph();
      closeListsTo(0);
      html.push("<hr>");
      continue;
    }

    if (trimmed.startsWith("> ") || trimmed === ">") {
      flushParagraph();
      closeListsTo(0);
      const quoted = [];
      while (i < lines.length && (lines[i].trim().startsWith("> ") || lines[i].trim() === ">")) {
        quoted.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      i -= 1;
      html.push(`<blockquote>${quoted.map(renderInline).join("<br>")}</blockquote>`);
      continue;
    }

    const listMatch = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
    if (listMatch) {
      flushParagraph();
      const indent = Math.floor(listMatch[1].length / 2);
      const type = /^[-*+]$/.test(listMatch[2]) ? "ul" : "ol";
      while (listStack.length > indent + 1) closeListsTo(listStack.length - 1);
      if (listStack.length === indent + 1 && listStack[listStack.length - 1].type !== type) {
        closeListsTo(indent);
      }
      while (listStack.length < indent + 1) {
        listStack.push({ type });
        html.push(`<${type}>`);
      }
      html.push(`<li>${renderInline(listMatch[3])}</li>`);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      closeListsTo(0);
      continue;
    }

    if (listStack.length) closeListsTo(0);
    paragraph.push(trimmed);
  }

  flushParagraph();
  closeListsTo(0);
  return html.join("");
}

function renderMarkdown(text) {
  const blocks = [];
  const pattern = /```([\w+-]+)?\n?([\s\S]*?)(?:```|$)/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      blocks.push({ type: "text", value: text.slice(cursor, match.index) });
    }
    blocks.push({ type: "code", language: match[1] || "", value: match[2] || "" });
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) blocks.push({ type: "text", value: text.slice(cursor) });
  if (!blocks.length) blocks.push({ type: "text", value: text });

  return blocks
    .map((block) =>
      block.type === "code"
        ? renderCodeBlock(block.language, block.value)
        : `<div class="markdown-block">${renderTextBlocks(block.value)}</div>`,
    )
    .join("");
}

/* --------------------------------------------------------------------------
   State helpers
   -------------------------------------------------------------------------- */

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

function applyConversationTitle(conversationId, title) {
  if (!title) return;
  const conversation = state.conversations.find((item) => item.id === conversationId);
  if (conversation && conversation.title !== title) {
    conversation.title = title;
    renderConversations();
    updateThreadTitle();
  }
}

function selectModel(value, persist = true) {
  const option = modelOptions().find(
    (item) => item.value === value && !item.disabled,
  ) || modelOptions().find((item) => !item.disabled);
  if (!option) {
    state.selectedProvider = "";
    state.selectedModel = "";
    state.selectedModelLabel = "No model configured";
    elements.modelSwitcher.disabled = true;
    elements.modelPickerBtn.disabled = true;
    syncModelPickerSelection();
    updateSendButton();
    elements.modelHint.textContent = "Ask an admin to configure a provider API key";
    return;
  }
  elements.modelSwitcher.value = option.value;
  state.selectedProvider = option.dataset.provider || "";
  state.selectedModel = option.dataset.model || "";
  state.selectedModelLabel = option.dataset.label || option.textContent.trim();
  elements.threadSubtitle.textContent = state.selectedModelLabel;
  elements.modelHint.textContent = DEFAULT_HINT;
  syncModelPickerSelection();
  updateSendButton();
  if (persist) localStorage.setItem("chat-model", option.value);
}

function setStreaming(isStreaming) {
  state.streaming = isStreaming;
  updateSendButton();
  elements.stopBtn.classList.toggle("hidden", !isStreaming);
  elements.stopBtn.disabled = false;
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

function removeTypingPlaceholder() {
  if (!state.typingMessageId) return;
  state.messages = state.messages.filter((item) => item.id !== state.typingMessageId);
  state.typingMessageId = null;
}

function finishFailedStream() {
  removeTypingPlaceholder();
  state.messages.forEach((message) => {
    if (message.streaming) message.streaming = false;
  });
}

/* --------------------------------------------------------------------------
   Rendering
   -------------------------------------------------------------------------- */

function renderConversations() {
  const activeId = state.activeConversationId;
  if (!state.conversations.length) {
    elements.conversationList.innerHTML = `
      <div class="conversation-empty">
        <span aria-hidden="true">✦</span>
        Your conversations will appear here.
      </div>
    `;
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
          <button class="conversation-more" type="button" data-id="${conversation.id}" title="Rename" aria-label="Rename">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m4 16-1 5 5-1L19 9l-4-4zM13.5 6.5l4 4"/></svg>
          </button>
          <button class="conversation-delete" type="button" data-id="${conversation.id}" title="Delete" aria-label="Delete">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6"/></svg>
          </button>
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

function renderMessageBody(message) {
  if (message.typing) return renderTypingIndicator();
  if (message.role === "assistant") {
    const rendered = renderMarkdown(message.content || "");
    return message.streaming ? `${rendered}<span class="stream-cursor"></span>` : rendered;
  }
  return `<div class="markdown-block">${escapeHtml(message.content || "")}</div>`;
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

      const copyButton = message.content
        ? `<button class="message-copy" type="button" data-copy="${encodeURIComponent(message.content)}">Copy</button>`
        : "";

      const retry = message.retryable ? '<button class="retry-btn" type="button">Retry</button>' : "";
      const metaParts = [];
      if (message.role === "assistant" && message.model) metaParts.push(modelLabelForId(message.model));
      metaParts.push(formatClockTime(message.createdAt));
      return `
        <article class="${classes}" data-id="${message.id || ""}">
          ${copyButton}
          <div class="message-body">${renderMessageBody(message)}</div>
          <div class="message-meta">${metaParts.filter(Boolean).join(" · ")}</div>
          ${retry}
        </article>
      `;
    })
    .join("");

  elements.jumpLatestBtn.classList.toggle("hidden", state.autoScroll);
  scrollToBottom();
}

// During streaming, update only the streaming message node so the rest of
// the thread doesn't re-render on every token.
function patchStreamingMessage(messageId) {
  const message = state.messages.find((item) => item.id === messageId);
  if (!message) return;
  const node = elements.messageList.querySelector(`[data-id="${messageId}"] .message-body`);
  if (!node) {
    renderMessages();
    return;
  }
  node.innerHTML = renderMessageBody(message);
  scrollToBottom();
}

function autosizeTextarea() {
  const node = elements.input;
  node.style.height = "auto";
  node.style.height = `${Math.min(node.scrollHeight, 190)}px`;
  updateSendButton();
}

/* --------------------------------------------------------------------------
   API
   -------------------------------------------------------------------------- */

async function listConversations(selectFallback = true) {
  const response = await apiFetch(API.conversations);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Failed to load conversations");
  state.conversations = data.items || [];
  if (selectFallback && !state.activeConversationId && state.conversations.length) {
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

function startNewChat() {
  state.activeConversationId = null;
  state.messages = [];
  state.autoScroll = true;
  state.lastFailedContent = "";
  state.lastFailedMessageIds = [];
  renderConversations();
  renderMessages();
  updateThreadTitle();
  elements.input.value = "";
  autosizeTextarea();
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

/* --------------------------------------------------------------------------
   Streaming send
   -------------------------------------------------------------------------- */

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
  const assistantMessage = {
    id: messageId,
    role: "assistant",
    content: initialChunk,
    createdAt: new Date().toISOString(),
    streaming: true,
    model: state.selectedModel,
  };
  if (idx >= 0) state.messages[idx] = assistantMessage;
  else state.messages.push(assistantMessage);
  state.typingMessageId = null;
  renderMessages();
}

function upsertStreamingAssistant(messageId, chunk) {
  const index = state.messages.findIndex((item) => item.id === messageId);
  if (index === -1) {
    replaceTypingWithAssistant(messageId, chunk);
    return;
  }
  state.messages[index].content += chunk;
  state.messages[index].streaming = true;
  patchStreamingMessage(messageId);
}

function finishStreamingAssistant(messageId, fullText) {
  const index = state.messages.findIndex((item) => item.id === messageId);
  if (index === -1) {
    state.messages.push({
      id: messageId,
      role: "assistant",
      content: fullText || "",
      createdAt: new Date().toISOString(),
      model: state.selectedModel,
    });
  } else {
    state.messages[index].content = fullText ?? state.messages[index].content;
    state.messages[index].streaming = false;
  }
  state.typingMessageId = null;
  renderMessages();
}

async function cancelStreaming() {
  elements.stopBtn.disabled = true;
  if (state.activeRequestId) {
    await apiFetch(API.cancel, {
      method: "POST",
      body: JSON.stringify({ requestId: state.activeRequestId }),
    });
  } else if (state.activeRequestController) {
    state.activeRequestController.abort();
  }
}

function parseSseChunk(buffer, onEvent) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
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
  if (!content || state.streaming) return;
  if (!getActiveConversation()) {
    try {
      await createConversation();
    } catch (error) {
      addInlineError(error.message || "Failed to create conversation");
      return;
    }
  }
  const conversation = getActiveConversation();
  if (!conversation) return;
  const requestConversationId = conversation.id;

  state.lastFailedContent = content;
  const userMessageId = `user-${Date.now()}`;
  state.messages.push({
    id: userMessageId,
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
  state.streamingConversationId = requestConversationId;
  state.activeRequestController = new AbortController();

  let assistantMessageId = `assistant-${Date.now()}`;
  let sawTerminal = false;
  try {
    const response = await apiFetch(`${API.conversations}/${conversation.id}/messages`, {
      method: "POST",
      signal: state.activeRequestController.signal,
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
          applyConversationTitle(conversation.id, data.title);
        } else if (eventName === "delta") {
          if (state.activeConversationId !== requestConversationId) return;
          if (!sawDelta) {
            replaceTypingWithAssistant(assistantMessageId, "");
            sawDelta = true;
          }
          upsertStreamingAssistant(assistantMessageId, data.text || "");
        } else if (eventName === "done") {
          sawTerminal = true;
          state.lastFailedMessageIds = [];
          if (state.activeConversationId === requestConversationId) {
            finishStreamingAssistant(assistantMessageId, data.fullText || "");
          }
          applyConversationTitle(conversation.id, data.title);
          state.activeRequestId = null;
        } else if (eventName === "error") {
          sawTerminal = true;
          state.lastFailedMessageIds = [userMessageId, assistantMessageId];
          state.activeRequestId = null;
          if (state.activeConversationId === requestConversationId) {
            finishFailedStream();
            addInlineError(data.message || "Generation failed", true);
          }
        }
      });
    }
    pending += decoder.decode();
    if (pending.trim()) {
      parseSseChunk(`${pending}\n\n`, (eventName, data) => {
        if (eventName === "done") {
          sawTerminal = true;
          state.lastFailedMessageIds = [];
          if (state.activeConversationId === requestConversationId) {
            finishStreamingAssistant(assistantMessageId, data.fullText || "");
          }
          applyConversationTitle(conversation.id, data.title);
        } else if (eventName === "error") {
          sawTerminal = true;
          state.lastFailedMessageIds = [userMessageId, assistantMessageId];
          if (state.activeConversationId === requestConversationId) {
            finishFailedStream();
            addInlineError(data.message || "Generation failed", true);
          }
        }
      });
    }
    if (!sawTerminal) throw new Error("The connection ended before the response completed");
    await listConversations(false);
  } catch (error) {
    if (state.activeConversationId === requestConversationId) {
      state.lastFailedMessageIds = [userMessageId, assistantMessageId];
      finishFailedStream();
      const message = error.name === "AbortError" ? "Generation stopped" : error.message || "Network error";
      addInlineError(message, error.name !== "AbortError");
    }
  } finally {
    state.activeRequestId = null;
    state.activeRequestController = null;
    state.streamingConversationId = null;
    setStreaming(false);
  }
}

/* --------------------------------------------------------------------------
   Events + bootstrap
   -------------------------------------------------------------------------- */

function bindEvents() {
  elements.newChatBtn.addEventListener("click", async () => {
    startNewChat();
    if (window.innerWidth <= 960) setSidebarOpen(false);
    elements.input.focus();
  });

  elements.sendBtn.addEventListener("click", sendMessage);
  elements.modelSwitcher?.addEventListener("change", () => selectModel(elements.modelSwitcher.value));
  elements.modelPickerBtn?.addEventListener("click", () => {
    const isOpen = elements.modelPickerBtn.getAttribute("aria-expanded") === "true";
    setModelPickerOpen(!isOpen);
  });
  elements.modelPickerMenu?.addEventListener("click", (event) => {
    const option = event.target.closest(".model-picker-option");
    if (!option || option.disabled) return;
    selectModel(option.dataset.value);
    setModelPickerOpen(false);
    elements.input.focus();
  });
  document.addEventListener("click", (event) => {
    if (!elements.modelPickerMenu || elements.modelPickerMenu.classList.contains("hidden")) return;
    if (event.target.closest(".model-switcher-wrap")) return;
    setModelPickerOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setModelPickerOpen(false);
  });
  elements.stopBtn.addEventListener("click", async () => {
    try {
      await cancelStreaming();
    } catch (_error) {
      elements.stopBtn.disabled = false;
    }
  });
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
      await copyText(value);
      copyCodeBtn.textContent = "Copied";
      setTimeout(() => {
        copyCodeBtn.textContent = "Copy";
      }, 1200);
      return;
    }

    const copyMessageBtn = event.target.closest(".message-copy");
    if (copyMessageBtn) {
      const value = decodeURIComponent(copyMessageBtn.dataset.copy || "");
      await copyText(value);
      copyMessageBtn.textContent = "Copied";
      setTimeout(() => {
        copyMessageBtn.textContent = "Copy";
      }, 1200);
      return;
    }

    const retryBtn = event.target.closest(".retry-btn");
    if (retryBtn) {
      const failedIds = new Set(state.lastFailedMessageIds);
      state.messages = state.messages.filter(
        (message) => !failedIds.has(message.id) && !message.retryable,
      );
      renderMessages();
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

  document.querySelectorAll("[data-chat-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      elements.input.value = button.dataset.chatPrompt || "";
      autosizeTextarea();
      elements.input.focus();
    });
  });
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const node = document.createElement("textarea");
  node.value = value;
  node.style.position = "fixed";
  node.style.opacity = "0";
  document.body.appendChild(node);
  node.select();
  document.execCommand("copy");
  node.remove();
}

async function bootstrap() {
  renderModelPicker();
  bindEvents();
  autosizeTextarea();
  selectModel(localStorage.getItem("chat-model") || elements.modelSwitcher?.value || "", false);

  try {
    await listConversations();
    if (state.activeConversationId) await loadMessages(state.activeConversationId);
    else renderMessages();
  } catch (error) {
    addInlineError(error.message || "Failed to load chat");
  }
  elements.input.focus();
}

bootstrap();
