/*
 * Property Advisor chat widget.
 * Add to any website, just before </body>:
 *   <script src="https://YOUR-SERVER/widget.js" data-color="#0d6b5a" data-title="Ask about your next home" defer></script>
 */
(function () {
  if (window.__propertyAdvisorLoaded) return;
  window.__propertyAdvisorLoaded = true;

  var script = document.currentScript || document.querySelector('script[src*="widget.js"]');
  var API = new URL(script.src).origin;
  var COLOR = script.getAttribute("data-color") || "#0d6b5a";
  var TITLE = script.getAttribute("data-title") || "";
  var STORE = "pa_session";

  var host = document.createElement("div");
  host.style.cssText = "position:fixed;z-index:2147483000;right:0;bottom:0;";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  root.innerHTML =
    '<style>' +
    ':host{all:initial}' +
    '*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}' +
    '.launch{position:fixed;right:max(20px,env(safe-area-inset-right));bottom:max(20px,env(safe-area-inset-bottom));display:flex;align-items:center;gap:8px;border:0;border-radius:999px;padding:14px 20px;background:' + COLOR + ';color:#fff;font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 6px 24px rgba(0,0,0,.2)}' +
    '.launch svg{width:20px;height:20px}' +
    '.panel{position:fixed;right:max(20px,env(safe-area-inset-right));bottom:max(20px,env(safe-area-inset-bottom));width:380px;max-width:calc(100vw - 24px);height:600px;max-height:calc(100vh - 40px);background:#fff;color:#14232a;border-radius:16px;box-shadow:0 12px 48px rgba(0,0,0,.25);display:flex;flex-direction:column;overflow:hidden}' +
    '.panel[hidden],.launch[hidden]{display:none}' +
    '.head{background:' + COLOR + ';color:#fff;padding:14px 16px;display:flex;align-items:center;justify-content:space-between;gap:8px}' +
    '.head b{font-size:16px}.head small{display:block;opacity:.85;font-size:12px;margin-top:2px}' +
    '.head button{background:transparent;border:0;color:#fff;font-size:24px;line-height:1;cursor:pointer;padding:4px 8px}' +
    '.thread{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#f4f6f6}' +
    '.msg{max-width:86%;padding:9px 13px;border-radius:14px;font-size:14px;line-height:1.5;overflow-wrap:anywhere}' +
    '.bot{background:#fff;border:1px solid #e1e7e6;align-self:flex-start;border-bottom-left-radius:4px}' +
    '.user{background:' + COLOR + ';color:#fff;align-self:flex-end;border-bottom-right-radius:4px;white-space:pre-wrap}' +
    '.msg p{margin:0 0 6px}.msg p:last-child{margin:0}.msg ul{margin:4px 0 6px;padding-left:18px}.msg li{margin:2px 0}' +
    '.typing{align-self:flex-start;font-size:13px;color:#5a6b70;padding:4px 2px}' +
    '.err{align-self:center;font-size:13px;color:#b2382f;text-align:center}' +
    '.chips{display:flex;flex-wrap:wrap;gap:6px}' +
    '.chip{border:1px solid #d5dedd;background:#fff;border-radius:999px;padding:6px 11px;font-size:13px;cursor:pointer;color:#14232a;text-align:left}' +
    '.chip:hover{border-color:' + COLOR + '}' +
    '.compose{display:flex;gap:8px;padding:10px;border-top:1px solid #e1e7e6;background:#fff}' +
    '.compose textarea{flex:1;resize:none;border:1px solid #d5dedd;border-radius:10px;padding:9px 11px;font-size:14px;max-height:110px;color:#14232a;background:#fff}' +
    '.compose button{border:0;border-radius:10px;padding:0 16px;background:' + COLOR + ';color:#fff;font-weight:600;cursor:pointer}' +
    '.compose button:disabled{opacity:.5;cursor:default}' +
    '.foot{font-size:11px;color:#7a8a8e;text-align:center;padding:0 10px 8px;background:#fff}' +
    'button:focus-visible,textarea:focus-visible{outline:2px solid ' + COLOR + ';outline-offset:2px}' +
    '@media (max-width:480px){.panel{right:0;bottom:0;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0}}' +
    '</style>' +
    '<button class="launch" aria-label="Open chat"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span class="lt">Find your next home</span></button>' +
    '<div class="panel" hidden role="dialog" aria-label="Property advisor chat">' +
    '  <div class="head"><div><b class="name">Property Advisor</b><small>Typically replies in a few seconds</small></div><button class="close" aria-label="Close chat">&times;</button></div>' +
    '  <div class="thread" aria-live="polite"></div>' +
    '  <div class="compose"><textarea rows="1" placeholder="Type your message…" aria-label="Message"></textarea><button class="send">Send</button></div>' +
    '  <div class="foot">Indicative guidance only. Not financial advice.</div>' +
    '</div>';

  var $ = function (s) { return root.querySelector(s); };
  var launch = $(".launch"), panel = $(".panel"), thread = $(".thread"), input = $("textarea"), sendBtn = $(".send");
  if (TITLE) $(".lt").textContent = TITLE;

  var sessionId = null;
  try { sessionId = sessionStorage.getItem(STORE); } catch (e) {}
  var started = false, busy = false;
  var STARTERS = [
    "We're a Singaporean couple looking to upgrade from our HDB",
    "First-time buyer, what can I afford?",
    "I'm a foreigner, what can I buy?"
  ];

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function md(text) {
    var out = "", inList = false;
    esc(text).split("\n").forEach(function (line) {
      var li = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
      var fmt = function (s) { return s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/^#{1,4}\s+/, ""); };
      if (li) { if (!inList) { out += "<ul>"; inList = true; } out += "<li>" + fmt(li[1]) + "</li>"; return; }
      if (inList) { out += "</ul>"; inList = false; }
      if (line.trim()) out += "<p>" + fmt(line) + "</p>";
    });
    return out + (inList ? "</ul>" : "");
  }
  function add(cls, text) {
    var el = document.createElement("div");
    el.className = cls === "user" || cls === "bot" ? "msg " + cls : cls;
    if (cls === "bot") el.innerHTML = md(text); else el.textContent = text;
    thread.appendChild(el); thread.scrollTop = thread.scrollHeight;
    return el;
  }

  function start() {
    if (started) return; started = true;
    fetch(API + "/api/config").then(function (r) { return r.json(); }).then(function (cfg) {
      $(".name").textContent = cfg.agent_name;
      add("bot", cfg.greeting);
      var chips = document.createElement("div"); chips.className = "chips";
      STARTERS.forEach(function (s) {
        var b = document.createElement("button"); b.className = "chip"; b.textContent = s;
        b.onclick = function () { send(s); }; chips.appendChild(b);
      });
      thread.appendChild(chips);
    }).catch(function () { add("err", "Chat is unavailable right now. Please try again later."); });
  }

  function send(text) {
    text = (text || input.value).trim();
    if (!text || busy) return;
    var chips = root.querySelector(".chips"); if (chips) chips.remove();
    busy = true; sendBtn.disabled = true; input.value = ""; input.style.height = "auto";
    add("user", text);
    var typing = add("typing", "Advisor is typing…");
    fetch(API + "/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text })
    }).then(function (r) {
      return r.json().then(function (data) { if (!r.ok) throw new Error(data.detail || "Something went wrong."); return data; });
    }).then(function (data) {
      sessionId = data.session_id;
      try { sessionStorage.setItem(STORE, sessionId); } catch (e) {}
      typing.remove(); add("bot", data.reply);
    }).catch(function (e) {
      typing.remove(); add("err", e.message || "Couldn't send. Please try again.");
    }).then(function () { busy = false; sendBtn.disabled = false; input.focus(); });
  }

  launch.onclick = function () { panel.hidden = false; launch.hidden = true; start(); input.focus(); };
  $(".close").onclick = function () { panel.hidden = true; launch.hidden = false; };
  sendBtn.onclick = function () { send(); };
  input.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  input.addEventListener("input", function () { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 110) + "px"; });
})();
