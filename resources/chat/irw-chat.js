/**
 * js for IRW Chat widget: agentic assistant to locate and process IRW data.
 * Configure API URL via window.IRW_CHAT_API_URL (default /api/chat for same-origin). (not perfect but works pretty well for now)
 */
(function () {
  "use strict";

  var API_URL = window.IRW_CHAT_API_URL || "/api/chat";
  var ROOT_ID = "irw-chat-root";
  var STORAGE_KEY = "irw-chat-panel-size";
  var DEFAULT_WIDTH = 380;
  var DEFAULT_HEIGHT = 520;
  var MIN_WIDTH = 320;
  var MIN_HEIGHT = 320;
  var MAX_WIDTH = 600;

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function renderMarkdownLite(text) {
    if (!text) return "";
    var codeBlocks = [];
    var idx = 0;
    // Extract fenced code blocks (``` or ``) so we don't escape or mangle them
    var rest = text.replace(/(```[\w]*\n[\s\S]*?```)/g, function (match) {
      var placeholder = "___CODE" + idx + "___";
      var inner = match.replace(/^```[\w]*\n/, "").replace(/\n```$/, "");
      codeBlocks[idx] = "<pre class=\"irw-chat-pre\"><code>" + escapeHtml(inner) + "</code></pre>";
      idx++;
      return placeholder;
    });
    rest = rest.replace(/(``[\w]*\n[\s\S]*?``)/g, function (match) {
      var placeholder = "___CODE" + idx + "___";
      var inner = match.replace(/^``[\w]*\n/, "").replace(/\n``$/, "");
      codeBlocks[idx] = "<pre class=\"irw-chat-pre\"><code>" + escapeHtml(inner) + "</code></pre>";
      idx++;
      return placeholder;
    });
    rest = escapeHtml(rest);
    // Headers (at line start or after newline) — match ### then ## then #
    rest = rest.replace(/(^|\n)###\s+([^\n]+)/g, "$1<h3 class=\"irw-chat-h3\">$2</h3>");
    rest = rest.replace(/(^|\n)##\s+([^\n]+)/g, "$1<h2 class=\"irw-chat-h2\">$2</h2>");
    rest = rest.replace(/(^|\n)#\s+([^\n]+)/g, "$1<h2 class=\"irw-chat-h2\">$2</h2>");
    // Links [text](url)
    rest = rest.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    // Bold and inline code
    rest = rest.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    rest = rest.replace(/`([^`]+)`/g, "<code class=\"irw-chat-inline-code\">$1</code>");
    // Numbered line "N. title" = standalone header (no bullet, no list indent). Bullets = <ul><li>.
    // Only treat a line as continuation of a list item when it doesn't look like a new paragraph.
    var lines = rest.split("\n");
    var out = [];
    var inUl = false;
    var looksLikeNewParagraph = function (s) {
      var t = s.trim();
      return !t || /^(For |See |To |You |We |I |Note |Click |If you |\[|Alternatively|Finally|In summary|R code|Code to|```)/i.test(t);
    };
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.trim() === "") {
        continue;
      }
      var numMatch = line.match(/^(\d+)\.\s+(.+)$/);
      var bulletMatch = line.match(/^\s*[-*]\s+(.+)$/);
      if (numMatch) {
        if (inUl) { out.push("</ul>"); inUl = false; }
        out.push("<div class=\"irw-chat-list-title\">" + numMatch[1] + ". " + numMatch[2] + "</div>");
      } else if (bulletMatch) {
        if (!inUl) { out.push("<ul class=\"irw-chat-list\">"); inUl = true; }
        out.push("<li>" + bulletMatch[1] + "</li>");
      } else {
        if (inUl && !looksLikeNewParagraph(line)) {
          var j = out.length - 1;
          while (j >= 0 && out[j].indexOf("<li>") !== 0) j--;
          if (j >= 0) {
            out[j] = out[j].replace("</li>", "<br>" + line + "</li>");
            continue;
          }
        }
        if (inUl) { out.push("</ul>"); inUl = false; }
        out.push(line);
      }
    }
    if (inUl) out.push("</ul>");
    rest = out.join("\n");
    rest = rest.replace(/\n{2,}/g, "\n").replace(/\n/g, "<br>");
    // Remove <br> between list elements so list items don't get double spacing
    rest = rest.replace(/(<\/li>)(<br>)+(<li>)/gi, "$1$3");
    rest = rest.replace(/(<\/li>)(<br>)+(<\/ul>)/gi, "$1$3");
    rest = rest.replace(/(<ul[^>]*>)(<br>)+(<li>)/gi, "$1$3");
    // Collapse extra <br> before/after list or title: at most one line break before, none after
    rest = rest.replace(/(<br>){2,}(<ul[^>]*>)/gi, "<br>$2");
    rest = rest.replace(/(<br>){2,}(<div class="irw-chat-list-title">)/gi, "<br>$2");
    rest = rest.replace(/(<\/ul>)(<br>)+/gi, "$1");
    rest = rest.replace(/(<\/div>)(<br>)+/gi, "$1");
    // Restore code blocks
    for (var j = 0; j < codeBlocks.length; j++) {
      rest = rest.replace("___CODE" + j + "___", codeBlocks[j]);
    }
    return rest;
  }

  function createRoot() {
    if (document.getElementById(ROOT_ID)) return document.getElementById(ROOT_ID);
    var root = document.createElement("div");
    root.id = ROOT_ID;
    root.innerHTML =
      '<button type="button" id="irw-chat-toggle" aria-label="Open IRW assistant">' +
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
      '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' +
      "</svg></button>" +
      '<div id="irw-chat-panel">' +
      '<div id="irw-chat-resize-handle" aria-label="Resize chat panel"></div>' +
      '<div id="irw-chat-header">' +
      '<span>IRW Data Assistant</span>' +
      '<button type="button" id="irw-chat-close" aria-label="Close">✕</button>' +
      "</div>" +
      '<div id="irw-chat-messages"></div>' +
      '<div id="irw-chat-input-area">' +
      '<form id="irw-chat-form">' +
      '<textarea id="irw-chat-input" rows="2" placeholder="Describe your project or data needs…" aria-label="Message"></textarea>' +
      '<button type="submit" id="irw-chat-send">Send</button>' +
      "</form>" +
      "</div>" +
      '<div id="irw-chat-error"></div>' +
      "</div>";
    document.body.appendChild(root);
    return root;
  }

  function appendMessage(container, role, content, isHtml) {
    var div = document.createElement("div");
    div.className = "irw-chat-msg " + role;
    div.innerHTML = isHtml ? content : renderMarkdownLite(content);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  function setError(root, msg) {
    var el = root.querySelector("#irw-chat-error");
    if (el) {
      el.textContent = msg || "";
      root.classList.toggle("error", !!msg);
    }
  }

  function getStoredSize() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        var w = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Number(parsed.w) || DEFAULT_WIDTH));
        var maxH = Math.min(window.innerHeight - 120, 800);
        var h = Math.max(MIN_HEIGHT, Math.min(maxH, Number(parsed.h) || DEFAULT_HEIGHT));
        return { w: w, h: h };
      }
    } catch (e) {}
    return { w: DEFAULT_WIDTH, h: DEFAULT_HEIGHT };
  }

  function saveSize(w, h) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ w: w, h: h }));
    } catch (e) {}
  }

  function setupResize(root) {
    var panel = root.querySelector("#irw-chat-panel");
    var handle = root.querySelector("#irw-chat-resize-handle");
    if (!panel || !handle) return;

    var saved = getStoredSize();
    panel.style.width = saved.w + "px";
    panel.style.height = saved.h + "px";

    var startX, startY, startW, startH;

    function onMouseMove(e) {
      var dw = startX - e.clientX;
      var dh = startY - e.clientY;
      var newW = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startW + dw));
      var maxH = Math.min(window.innerHeight - 120, 800);
      var newH = Math.max(MIN_HEIGHT, Math.min(maxH, startH + dh));
      panel.style.width = newW + "px";
      panel.style.height = newH + "px";
    }

    function onMouseUp() {
      root.classList.remove("resizing");
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      var w = parseInt(panel.style.width, 10);
      var h = parseInt(panel.style.height, 10);
      if (!isNaN(w) && !isNaN(h)) saveSize(w, h);
    }

    handle.addEventListener("mousedown", function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      root.classList.add("resizing");
      startX = e.clientX;
      startY = e.clientY;
      startW = panel.offsetWidth;
      startH = panel.offsetHeight;
      document.body.style.cursor = "nwse-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    });
  }

  function init() {
    var root = createRoot();
    setupResize(root);
    var toggle = root.querySelector("#irw-chat-toggle");
    var panel = root.querySelector("#irw-chat-panel");
    var closeBtn = root.querySelector("#irw-chat-close");
    var messagesEl = root.querySelector("#irw-chat-messages");
    var form = root.querySelector("#irw-chat-form");
    var input = root.querySelector("#irw-chat-input");
    var sendBtn = root.querySelector("#irw-chat-send");

    var history = [];

    toggle.addEventListener("click", function () {
      root.classList.add("open");
      input.focus();
    });
    closeBtn.addEventListener("click", function () {
      root.classList.remove("open");
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = (input.value || "").trim();
      if (!text || sendBtn.disabled) return;

      appendMessage(messagesEl, "user", text);
      input.value = "";
      sendBtn.disabled = true;
      setError(root, "");

      var typingEl = document.createElement("div");
      typingEl.className = "irw-chat-typing";
      typingEl.textContent = "Searching datasets and preparing recommendations…";
      messagesEl.appendChild(typingEl);
      messagesEl.scrollTop = messagesEl.scrollHeight;

      var body = { message: text, history: history };

      fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then(function (res) {
          if (!res.ok) throw new Error(res.statusText || "Request failed");
          return res.json();
        })
        .then(function (data) {
          typingEl.remove();
          if (data.reply) appendMessage(messagesEl, "assistant", data.reply);
          if (Array.isArray(data.history)) history = data.history;
          setError(root, "");
        })
        .catch(function (err) {
          typingEl.remove();
          var hint = "Is the backend running? Open " + API_URL.replace("/chat", "/health") + " in a new tab to check.";
          appendMessage(messagesEl, "assistant", "Sorry, the assistant is unavailable. " + hint);
          setError(root, "Failed to fetch (" + API_URL + "): " + err.message);
        })
        .finally(function () {
          sendBtn.disabled = false;
          input.focus();
        });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
