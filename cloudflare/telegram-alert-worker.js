const ALLOWED_ORIGIN = "https://arqanpharma11.github.io";
const ADMIN_UID = "qpuH4fWGhSYFq0mqTGfIEIn4VS13";
function cors(origin) {
  return {
    "Access-Control-Allow-Origin": origin === ALLOWED_ORIGIN ? ALLOWED_ORIGIN : "null",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Vary": "Origin"
  };
}

function json(data, status, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers }
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const headers = cors(origin);
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      if (origin !== ALLOWED_ORIGIN) return new Response(null, { status: 403 });
      return new Response(null, { status: 204, headers });
    }

    if (origin !== ALLOWED_ORIGIN) return json({ error: "Forbidden origin" }, 403, headers);
    if (request.method !== "POST") return json({ error: "Method not allowed" }, 405, headers);

    if (!env.FIREBASE_WEB_API_KEY || !env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
      return json({ error: "Worker is not fully configured" }, 503, headers);
    }

    const authorization = request.headers.get("Authorization") || "";
    const match = authorization.match(/^Bearer\s+(.+)$/i);
    if (!match) return json({ error: "Missing Firebase authentication" }, 401, headers);

    // Ask Firebase Identity Toolkit to validate the ID token, then enforce the single admin UID.
    let identity;
    try {
      const verifyResponse = await fetch(
        "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=" + encodeURIComponent(env.FIREBASE_WEB_API_KEY),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ idToken: match[1] })
        }
      );
      if (!verifyResponse.ok) return json({ error: "Invalid or expired Firebase token" }, 401, headers);
      identity = await verifyResponse.json();
    } catch (_) {
      return json({ error: "Could not verify Firebase identity" }, 502, headers);
    }

    const user = identity.users && identity.users[0];
    if (!user || user.localId !== ADMIN_UID || user.disabled === true) {
      return json({ error: "Admin only" }, 403, headers);
    }

    let body;
    try {
      body = await request.json();
    } catch (_) {
      return json({ error: "Invalid JSON" }, 400, headers);
    }

    const message = typeof body.message === "string" ? body.message.trim() : "";
    if (!message || message.length > 3500) {
      return json({ error: "Message must contain 1 to 3500 characters" }, 400, headers);
    }

    try {
      const telegramResponse = await fetch(
        "https://api.telegram.org/bot" + env.TELEGRAM_BOT_TOKEN.trim() + "/sendMessage",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: env.TELEGRAM_CHAT_ID.trim(),
            text: message,
            disable_web_page_preview: true
          })
        }
      );
      const telegramResult = await telegramResponse.json();
      if (!telegramResponse.ok || !telegramResult.ok) {
        return json({ error: "Telegram delivery failed" }, 502, headers);
      }
      return json({ ok: true }, 200, headers);
    } catch (_) {
      return json({ error: "Telegram service unavailable" }, 502, headers);
    }
  }
};
