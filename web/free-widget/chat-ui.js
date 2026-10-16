/* ================= Guided chat UI (no AI, no server) ================= */
var script = document.currentScript || document.querySelector('script[src*="property-chat"]') || { getAttribute: function () { return null; } };
var COLOR = script.getAttribute("data-color") || "#0d6b5a";
var TITLE = script.getAttribute("data-title") || "Find your next home";
var NAME = script.getAttribute("data-name") || "Property Advisor";
var WEBHOOK = script.getAttribute("data-webhook") || "";      // optional Google Apps Script / Zapier URL
var WHATSAPP = (script.getAttribute("data-whatsapp") || "").replace(/\D/g, ""); // optional, e.g. 6590000000
var OPEN = script.getAttribute("data-open") === "true";

var fmt = function (n) { return Math.round(n).toLocaleString("en-SG"); };
function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

/* Accepts 14000, 14k, $14,000, 1.2m, 650K */
function parseAmount(text) {
  var s = String(text).toLowerCase().replace(/[$,\s]|sgd|s\$/g, "");
  var m = s.match(/^(\d+(?:\.\d+)?)(k|m|mil|million)?$/);
  if (!m) return null;
  var n = parseFloat(m[1]);
  if (m[2] === "k") n *= 1e3; else if (m[2]) n *= 1e6;
  return n;
}

var host = document.createElement("div");
host.style.cssText = "position:fixed;z-index:2147483000;right:0;bottom:0;";
document.body.appendChild(host);
var root = host.attachShadow({ mode: "open" });
root.innerHTML =
  "<style>" +
  ":host{all:initial}*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}" +
  ".launch{position:fixed;right:max(20px,env(safe-area-inset-right));bottom:max(20px,env(safe-area-inset-bottom));display:flex;align-items:center;gap:8px;border:0;border-radius:999px;padding:14px 20px;background:" + COLOR + ";color:#fff;font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 6px 24px rgba(0,0,0,.2)}" +
  ".launch svg{width:20px;height:20px}.launch[hidden],.panel[hidden]{display:none}" +
  ".panel{position:fixed;right:max(20px,env(safe-area-inset-right));bottom:max(20px,env(safe-area-inset-bottom));width:390px;max-width:calc(100vw - 24px);height:620px;max-height:calc(100vh - 40px);background:#fff;color:#14232a;border-radius:16px;box-shadow:0 12px 48px rgba(0,0,0,.25);display:flex;flex-direction:column;overflow:hidden}" +
  ".head{background:" + COLOR + ";color:#fff;padding:12px 14px 12px 16px;display:flex;align-items:center;gap:6px}" +
  ".head div{flex:1;min-width:0}.head b{font-size:16px}.head small{display:block;opacity:.85;font-size:12px;margin-top:2px}" +
  ".head button{background:transparent;border:0;color:#fff;cursor:pointer;padding:6px 8px;border-radius:8px;font-size:13px}" +
  ".head button.x{font-size:24px;line-height:1}.head button:hover{background:rgba(255,255,255,.15)}" +
  ".thread{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#f4f6f6}" +
  ".msg{max-width:88%;padding:9px 13px;border-radius:14px;font-size:14px;line-height:1.5;overflow-wrap:anywhere}" +
  ".bot{background:#fff;border:1px solid #e1e7e6;align-self:flex-start;border-bottom-left-radius:4px}" +
  ".user{background:" + COLOR + ";color:#fff;align-self:flex-end;border-bottom-right-radius:4px}" +
  ".msg p{margin:0 0 6px}.msg p:last-child{margin:0}.msg small{color:#5a6b70}" +
  ".chips{display:flex;flex-wrap:wrap;gap:6px}" +
  ".chip{border:1px solid " + COLOR + ";background:#fff;color:" + COLOR + ";border-radius:999px;padding:7px 13px;font-size:13.5px;font-weight:600;cursor:pointer}" +
  ".chip:hover{background:" + COLOR + ";color:#fff}" +
  ".card{background:#fff;border:1px solid #e1e7e6;border-radius:12px;padding:11px 13px;font-size:13.5px;line-height:1.45;align-self:stretch}" +
  ".card.top{border:2px solid " + COLOR + "}" +
  ".card h4{margin:0 0 4px;font-size:15px;display:flex;justify-content:space-between;gap:8px;align-items:baseline}" +
  ".card h4 span{font-size:12px;font-weight:600;color:" + COLOR + ";white-space:nowrap}" +
  ".card ul{margin:6px 0 0;padding-left:16px;color:#5a6b70;font-size:12.5px}" +
  ".pill{display:inline-block;font-size:11px;font-weight:700;padding:1px 8px;border-radius:999px;margin-right:4px;text-transform:uppercase;letter-spacing:.04em}" +
  ".ok{background:#e3f3e9;color:#1d7a46}.warn{background:#fbf0dc;color:#9a5d06}.bad{background:#f9e4e2;color:#b2382f}" +
  ".out{color:#5a6b70;font-size:12.5px;align-self:stretch}.out b{color:#14232a}" +
  ".compose{display:flex;gap:8px;padding:10px;border-top:1px solid #e1e7e6;background:#fff}" +
  ".compose input{flex:1;min-width:0;border:1px solid #d5dedd;border-radius:10px;padding:10px 12px;font-size:15px;color:#14232a;background:#fff}" +
  ".compose button{border:0;border-radius:10px;padding:0 16px;background:" + COLOR + ";color:#fff;font-weight:600;cursor:pointer}" +
  ".compose[hidden]{display:none}.hint{font-size:12px;color:#b2382f;padding:0 12px 6px;background:#fff}.hint:empty{display:none}" +
  ".foot{font-size:11px;color:#7a8a8e;text-align:center;padding:4px 10px 8px;background:#fff}" +
  "a.wa{display:inline-block;background:#1f9e55;color:#fff;text-decoration:none;font-weight:600;padding:8px 14px;border-radius:999px;font-size:13.5px}" +
  "button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid " + COLOR + ";outline-offset:2px}" +
  "@media (max-width:480px){.panel{right:0;bottom:0;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0}}" +
  "</style>" +
  "<button class='launch' aria-label='Open chat'><svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/></svg><span class='lt'></span></button>" +
  "<div class='panel' hidden role='dialog' aria-label='Property advisor chat'>" +
  "<div class='head'><div><b class='nm'></b><small>Answer a few quick questions</small></div><button class='restart' aria-label='Start over'>Start over</button><button class='x' aria-label='Close chat'>&times;</button></div>" +
  "<div class='thread' aria-live='polite'></div>" +
  "<div class='hint'></div>" +
  "<form class='compose' hidden><input autocomplete='off' aria-label='Your answer'><button type='submit'>Send</button></form>" +
  "<div class='foot'>Indicative guidance only. Not financial advice.</div></div>";

var $ = function (s) { return root.querySelector(s); };
var thread = $(".thread"), form = $(".compose"), input = $(".compose input"), hint = $(".hint");
$(".lt").textContent = TITLE; $(".nm").textContent = NAME;

function scroll() { thread.scrollTop = thread.scrollHeight; }
function say(html) { var el = document.createElement("div"); el.className = "msg bot"; el.innerHTML = html; thread.appendChild(el); scroll(); return el; }
function echo(text) { var el = document.createElement("div"); el.className = "msg user"; el.textContent = text; thread.appendChild(el); scroll(); }
function block(cls, html) { var el = document.createElement("div"); el.className = cls; el.innerHTML = html; thread.appendChild(el); scroll(); return el; }
function clearInputs() { var c = thread.querySelector(".chips:last-child"); if (c && c.dataset.live) c.remove(); form.hidden = true; hint.textContent = ""; }

/* Ask with buttons. options: [[label, value], ...] */
function choose(question, options, onPick) {
  say(question);
  var wrap = document.createElement("div"); wrap.className = "chips"; wrap.dataset.live = "1";
  options.forEach(function (o) {
    var b = document.createElement("button"); b.className = "chip"; b.textContent = o[0];
    b.onclick = function () { clearInputs(); echo(o[0]); setTimeout(function () { onPick(o[1]); }, 250); };
    wrap.appendChild(b);
  });
  thread.appendChild(wrap); scroll();
}

/* Ask for typed text. validate returns {value} or {error} */
var pending = null;
function ask(question, placeholder, validate, onAnswer, quick) {
  say(question);
  if (quick) {
    var wrap = document.createElement("div"); wrap.className = "chips"; wrap.dataset.live = "1";
    quick.forEach(function (q) {
      var b = document.createElement("button"); b.className = "chip"; b.textContent = q[0];
      b.onclick = function () { clearInputs(); pending = null; echo(q[0]); setTimeout(function () { onAnswer(q[1]); }, 250); };
      wrap.appendChild(b);
    });
    thread.appendChild(wrap); scroll();
  }
  pending = { validate: validate, onAnswer: onAnswer };
  input.value = ""; input.placeholder = placeholder; form.hidden = false; input.focus();
}
form.addEventListener("submit", function (e) {
  e.preventDefault();
  if (!pending || !input.value.trim()) return;
  var r = pending.validate(input.value.trim());
  if (r.error) { hint.textContent = r.error; return; }
  var cb = pending.onAnswer; pending = null;
  echo(input.value.trim()); clearInputs();
  setTimeout(function () { cb(r.value); }, 250);
});
function money(min, max) {
  return function (t) {
    var n = parseAmount(t);
    if (n == null) return { error: "Please enter an amount, e.g. 12000 or 12k." };
    if (n < min || n > max) return { error: "That amount looks off. Please check and try again." };
    return { value: n };
  };
}
function years(min, max) {
  return function (t) {
    var n = parseFloat(String(t).replace(/[^\d.]/g, ""));
    if (!isFinite(n) || n < min || n > max) return { error: "Please enter a number between " + min + " and " + max + "." };
    return { value: n };
  };
}

/* ---------- The conversation ---------- */
var d, summaryText = "";
function start() {
  thread.innerHTML = ""; clearInputs(); pending = null; d = {}; summaryText = "";
  say("<p>Hi! I'll help you see which property type fits your next move: <b>HDB resale, new-launch EC, condo or landed</b>.</p><p>It takes about a minute. Let's start.</p>");
  setTimeout(function () {
    choose("Are you a <b>Singapore Citizen, PR or foreigner</b>?", [["Singapore Citizen", "SC"], ["PR", "PR"], ["Foreigner", "FOREIGNER"]], function (v) {
      d.residency = v; stepWho();
    });
  }, 400);
}
function stepWho() {
  choose("Are you buying alone or with someone?", [["Alone", "single"], ["With my spouse", "married_couple"], ["With family / partner", "other_joint"]], function (v) {
    d.household_type = v;
    if (v === "single") return stepAge();
    choose("What's their residency?", [["Singapore Citizen", "SC"], ["PR", "PR"], ["Foreigner", "FOREIGNER"]], function (r) {
      d.co_applicant_residency = r; stepAge();
    });
  });
}
function stepAge() {
  ask("How old are you?", "e.g. 35", years(21, 99), function (v) { d.age = Math.round(v); stepIncome(); });
}
function stepIncome() {
  ask("What's the <b>total gross monthly income</b> of everyone buying?", "e.g. 12000 or 12k", money(0, 1e6), function (v) {
    d.monthly_income = v; stepDebt();
  });
}
function stepDebt() {
  ask("Any other monthly loan repayments, like a car loan?", "e.g. 800", money(0, 1e6), function (v) {
    d.existing_monthly_debt = v; stepCpf();
  }, [["None", 0]]);
}
function stepCpf() {
  ask("Roughly how much is in your <b>CPF Ordinary Account</b> (combined)?", "e.g. 120k", money(0, 1e8), function (v) {
    d.cpf_oa_balance = v; stepCash();
  }, [["None", 0]]);
}
function stepCash() {
  ask("How much <b>cash</b> can you put towards the purchase?", "e.g. 80k", money(0, 1e9), function (v) {
    d.cash_savings = v; stepOwn();
  }, [["None", 0]]);
}
function stepOwn() {
  choose("Do you own a property now?", [["No", ""], ["HDB", "HDB"], ["EC", "EC"], ["Private condo", "PRIVATE"], ["Landed", "LANDED"]], function (v) {
    if (!v) return stepPurpose();
    d.current_property = { type: v };
    ask("What's it worth today, roughly?", "e.g. 650k", money(10000, 1e9), function (val) {
      d.current_property.estimated_value = val;
      ask("How much is left on the home loan?", "e.g. 180k", money(0, 1e9), function (loan) {
        d.current_property.outstanding_loan = loan;
        ask("How much CPF have you used for it, <b>including accrued interest</b>? <small>(On the CPF website: My Requests &gt; Home Ownership)</small>", "e.g. 200k", money(0, 1e9), function (cpf) {
          if (cpf === "estimate") { cpf = Math.round(val * 0.3); d.cpfEstimated = true; }
          d.current_property.cpf_used_with_interest = cpf;
          ask("How many years have you owned it?", "e.g. 6", years(0, 99), function (y) {
            d.current_property.years_owned = y;
            choose("Will you sell it or keep it?", [["Sell it", "sell"], ["Keep it", "keep"]], function (p) {
              d.current_property.plan = p; stepPurpose();
            });
          });
        }, [["Not sure", "estimate"]]);
      }, [["Fully paid", 0]]);
    });
  });
}
function stepPurpose() {
  choose("Is this for your own stay or for investment?", [["Own stay", "own_stay"], ["Investment", "investment"]], function (v) {
    d.purpose = v;
    choose("When do you need to move?", [["Soon (within a year)", "immediate"], ["I'm flexible", "flexible"]], function (t) {
      d.timeline = t; showResults();
    });
  });
}

function pill(r) {
  if (r.eligibility === "not_eligible") return "<span class='pill bad'>Not eligible</span>";
  var a = { comfortable: ["ok", "Comfortable"], stretch: ["warn", "Stretch"], out_of_reach: ["bad", "Over budget"] }[r.affordability];
  return (r.eligibility === "conditional" ? "<span class='pill warn'>Conditions</span>" : "") + "<span class='pill " + a[0] + "'>" + a[1] + "</span>";
}
function showResults() {
  var rep;
  try { rep = analyse(d); } catch (e) { say("Sorry, something didn't add up: " + esc(e.message) + ". Tap <b>Start over</b> to try again."); return; }
  var viable = rep.ranked_options.filter(function (r) { return r.eligibility !== "not_eligible" && r.affordability !== "out_of_reach"; });
  var out = rep.ranked_options.filter(function (r) { return viable.indexOf(r) < 0; });
  var f = rep.client_summary.funds_available;
  say("<p>Here's your first look. Your funds for the purchase come to about <b>S$" + fmt(f.cpf) + " CPF</b> and <b>S$" + fmt(f.cash) + " cash</b>" +
      (f.sale_cash_proceeds ? " (including your sale proceeds)" : "") + ".</p>" +
      (viable.length ? "<p>Best fit: <b>" + esc(viable[0].label) + "</b>.</p>" : "<p>None of the options fit comfortably right now. See the notes below; our agent can help you plan.</p>") +
      (d.cpfEstimated ? "<p><small>CPF used was estimated at 30% of the home's value. Check your actual figure for a better result.</small></p>" : ""));
  viable.slice(0, 3).forEach(function (r, i) {
    var a = r.max_affordable_price, ip = r.illustrative_purchase;
    var notes = r.eligibility_reasons.concat(r.notes).slice(0, 3);
    block("card" + (i === 0 ? " top" : ""),
      "<h4>" + esc(r.label) + "<span>" + r.suitability_score + "/100</span></h4>" + pill(r) +
      "<div style='margin-top:6px'>Budget up to <b>~S$" + fmt(a.max_price) + "</b></div>" +
      (ip ? "<div>e.g. S$" + fmt(ip.price) + " → about <b>S$" + fmt(ip.monthly_instalment) + "/month</b></div>" : "") +
      (a.absd ? "<div>ABSD: S$" + fmt(a.absd) + " (" + Math.round(a.absd_rate * 100) + "%)</div>" : "") +
      (notes.length ? "<ul>" + notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul>" : ""));
  });
  if (out.length) {
    block("out", "<b>Not suitable now:</b> " + out.map(function (r) {
      var why = r.eligibility === "not_eligible" ? r.eligibility_reasons[0] : "budget is below typical prices (" + r.price_band.note + ")";
      return esc(r.label) + ": " + esc(why);
    }).join("; ") + ".");
  }
  summaryText = "Profile: " + rep.client_summary.buyers.join(" + ") + ", age " + d.age + ", income $" + fmt(d.monthly_income) +
    "/mth, CPF $" + fmt(d.cpf_oa_balance) + ", cash $" + fmt(d.cash_savings) +
    (d.current_property ? ", owns " + d.current_property.type + " (" + d.current_property.plan + ")" : ", no property") +
    ". Top options: " + (viable.slice(0, 2).map(function (r) { return r.label + " up to $" + fmt(r.max_affordable_price.max_price); }).join(", ") || "none viable");
  setTimeout(stepLead, 600);
}

function waLink(name) {
  var text = "Hi" + (name ? ", I'm " + name : "") + ". I used the property chat on your website. " + summaryText;
  return "<a class='wa' target='_blank' rel='noopener' href='https://wa.me/" + WHATSAPP + "?text=" + encodeURIComponent(text) + "'>Send to our agent on WhatsApp</a>";
}
function stepLead() {
  if (!WEBHOOK && !WHATSAPP) {
    say("Want to go through specific projects? Contact our agent and mention your results above.");
    return;
  }
  choose("Would you like our agent to go through specific projects with you? No obligation.", [["Yes, contact me", "yes"], ["No thanks", "no"]], function (v) {
    if (v === "no") { say("No problem! Tap <b>Start over</b> anytime to try different numbers."); return; }
    if (!WEBHOOK) {
      // No lead sheet set up: hand the conversation over on WhatsApp with the summary pre-filled.
      say("<p>Tap below to send your results to our agent. Your summary is already filled in; just press send in WhatsApp.</p><p>" + waLink("") + "</p>");
      return;
    }
    ask("Great! What's your name?", "Your name", function (t) { return t.length < 2 ? { error: "Please enter your name." } : { value: t.slice(0, 100) }; }, function (name) {
      ask("And your mobile number?", "e.g. 9123 4567", function (t) {
        var digits = t.replace(/\D/g, "");
        return digits.length < 8 ? { error: "Please enter a valid phone number." } : { value: t.slice(0, 30) };
      }, function (phone) { saveLead(name, phone); });
    });
  });
}
function saveLead(name, phone) {
  var lead = { saved_at: new Date().toISOString(), name: name, phone: phone, email: "", preferred_contact_time: "", summary: summaryText };
  // text/plain avoids a CORS preflight, which Google Apps Script doesn't support
  fetch(WEBHOOK, { method: "POST", mode: "no-cors", headers: { "Content-Type": "text/plain" }, body: JSON.stringify(lead) })
    .then(function () {
      say("<p>Thanks, " + esc(name) + "! Our agent will be in touch soon.</p>" +
          (WHATSAPP ? "<p>Want a faster reply? " + waLink(name) + "</p>" : ""));
    })
    .catch(function () {
      say("<p>Sorry, we couldn't send your details.</p>" +
          (WHATSAPP ? "<p>" + waLink(name) + "</p>" : "<p>Please contact our agent directly.</p>"));
    });
}

var launch = $(".launch"), panel = $(".panel"), begun = false;
function openChat() { panel.hidden = false; launch.hidden = true; if (!begun) { begun = true; start(); } }
launch.onclick = openChat;
$(".x").onclick = function () { panel.hidden = true; launch.hidden = false; };
$(".restart").onclick = start;
if (OPEN) openChat();
