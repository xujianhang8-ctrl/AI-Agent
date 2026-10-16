# Free property chat widget

A guided chat for your website that asks clients about residency, income, CPF, cash and their
current home. It then recommends **HDB resale, new-launch EC, resale condo, new-launch condo or
landed**, with a budget and monthly instalment.

It runs entirely in the visitor's browser: **no AI, no server, no API key, no cost**.

## Try it

Open `demo.html` in your browser (double-click it), then click **Find your next home**.

## Add it to your website

1. Upload `property-chat.js` to your website. On WordPress, use Media → Add New, then copy the file's URL.
2. Paste this just before `</body>` (Wix: Settings → Custom Code; WordPress: the WPCode plugin;
   Squarespace: Code Injection → Footer):

```html
<script src="https://YOUR-SITE/property-chat.js"
        data-name="Your Agency"
        data-color="#0d6b5a"
        data-whatsapp="6591234567"
        defer></script>
```

| Option | What it does |
|---|---|
| `data-whatsapp` | **Your** WhatsApp number with the country code, no `+` or spaces. At the end of the chat, clients tap a button that opens WhatsApp with their results already typed out. |
| `data-webhook` | Optional. A Google Sheet web app URL (see `docs/google-sheets-leads.gs`). The chat then also asks for name and phone and saves each lead as a row in your sheet. |
| `data-name` | Name in the chat header. |
| `data-color` | Your brand colour. |
| `data-title` | Text on the chat button (default "Find your next home"). |
| `data-open` | `"true"` opens the chat as soon as the page loads. |

Set at least `data-whatsapp` or `data-webhook`, otherwise clients have no way to reach you from
the chat.

## Free vs AI version

| | Free (this) | AI version (`property_agent/server.py`) |
|---|---|---|
| Cost | Free | API usage (about S$0.20–0.60 per chat) + hosting |
| Conversation | Fixed questions with buttons | Free-form; answers follow-up questions like "what if we keep the HDB?" |
| Calculations | Same rules engine | Same rules engine |

## Editing

`property-chat.js` is generated. Edit `chat-ui.js` (the conversation) or `../engine.js` (the
calculator and policy numbers), then run `python web/free-widget/build.py`. If you change policy
numbers, update `property_agent/rules.py` to match.
