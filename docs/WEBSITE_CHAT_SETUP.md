# Put the chat on your website

You'll do four things, about 30 minutes in total:

1. Get a Claude API key
2. Put the chat server online with Render
3. Paste one line into your website
4. (Optional) Send leads to a Google Sheet

No coding needed. You will copy and paste a few values.

---

## 1. Get a Claude API key

1. Go to **console.anthropic.com** and sign up.
2. Open **Billing** and add credit. US$20 is plenty to start.
3. Under **Limits**, set a monthly spend limit (e.g. US$50) so costs can never run away.
4. Open **API Keys**, click **Create Key**, name it "website chat", and copy the key (it starts with `sk-ant-`).
   Keep it private: anyone with this key can spend your credit.

**Cost:** a full client conversation (8–12 messages including the analysis) costs roughly
**S$0.20–0.60**. To lower it, change `MODEL` in `property_agent/agent.py` to `claude-sonnet-5-5`,
which costs about half.

## 2. Put the chat server online (Render)

Render runs the server for you and gives it a web address.

1. Go to **render.com** and sign up **with your GitHub account**.
2. Click **New +** → **Blueprint**.
3. Pick the **AI-Agent** repository. For the branch, choose `main` if this code has been merged,
   otherwise `claude/determined-bardeen-f4k5ma`.
4. Render reads `render.yaml` and asks for these settings:

   | Setting | What to enter |
   |---|---|
   | `ANTHROPIC_API_KEY` | The key from step 1 |
   | `ALLOWED_ORIGINS` | Your website address(es), comma-separated, e.g. `https://www.myagency.sg,https://myagency.sg`. This stops other sites from using your chat (and your credit). |
   | `LEAD_WEBHOOK_URL` | Leave blank for now (see step 4) |

5. Click **Apply**. After 2–3 minutes you'll get an address like
   `https://property-advisor-chat.onrender.com`.
6. Open that address. You'll see a demo page with the chat button in the bottom-right corner.
   Try a conversation.

**Free plan vs paid:** the free plan works, but it goes to sleep after 15 minutes with no visitors.
The first message after that waits about 50 seconds. For a business site, upgrade the service to
**Starter** (about US$7/month) in the Render dashboard so it is always on.

## 3. Add the chat to your website

Copy the line shown on your demo page. It looks like this:

```html
<script src="https://property-advisor-chat.onrender.com/widget.js" data-color="#0d6b5a" data-title="Find your next home" defer></script>
```

- `data-color` is the button and header colour. Use your brand colour.
- `data-title` is the text on the chat button.

Where to paste it:

- **Wix:** Settings → Custom Code → **+ Add Custom Code** → paste → "Body - end" → All pages.
  (Needs a Wix premium plan with a connected domain.)
- **WordPress:** install the free **WPCode** plugin → Code Snippets → Header & Footer → paste into **Footer**.
- **Squarespace:** Settings → Advanced → **Code Injection** → paste into **Footer**.
- **Any other site:** paste just before `</body>` on every page.

## 4. Get leads into a Google Sheet (recommended)

When a client agrees to be contacted, the bot saves their name, phone number and a summary of their
situation. The server keeps a copy, but Render's disk is wiped whenever the server restarts, so send
leads to a Google Sheet as well:

1. Create a new Google Sheet, e.g. "Chat leads".
2. Click **Extensions → Apps Script**. Delete what's there and paste the contents of
   [`docs/google-sheets-leads.gs`](google-sheets-leads.gs). Click **Save**.
3. Click **Deploy → New deployment**. Click the gear icon and pick **Web app**. Set
   "Execute as" to **Me** and "Who has access" to **Anyone**. Click **Deploy** and allow access.
4. Copy the **Web app URL**.
5. In Render, open your service → **Environment** → set `LEAD_WEBHOOK_URL` to that URL → **Save**.
   Render restarts the server automatically.

Every new lead now appears as a row in your sheet. If you prefer email or WhatsApp alerts, the same
URL setting works with Zapier or Make: create a "Catch Hook" webhook there and paste its URL instead.

You can also view leads at `https://YOUR-SERVER/admin/leads?token=YOUR_ADMIN_TOKEN`. Render created
`ADMIN_TOKEN` for you; find it under **Environment**.

---

## Before going live

- Check the policy figures and price bands in `property_agent/rules.py` against IRAS, HDB and MAS.
- Have a few test conversations as different client types (SC upgrader, PR first-timer, foreigner).
- Under PDPA, tell visitors how you'll use their contact details. A line in your website's privacy
  policy covering "enquiries submitted through the chat assistant" is the usual approach.

## Built-in safeguards

- Your API key stays on the server and is never sent to browsers.
- Each visitor is limited to 20 messages per 10 minutes, and each chat to 40 messages.
- Messages are capped at 2,000 characters.
- Idle chats are cleared from memory after an hour.
