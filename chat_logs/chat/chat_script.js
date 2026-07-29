const WS_URL   = "ws://localhost:5001"; // chat_server.py WebSocket address
const MAX_MSGS = 25;                    // max messages visible before oldest are removed
const chat     = document.getElementById("chat");

// SVG icons for each platform — rendered inside the badge element
const ICONS = {
    twitch: `<svg xmlns="http://www.w3.org/2000/svg" width="16px" height="16px" fill="currentColor" viewBox="0 0 16 16"><path d="M3.857 0 1 2.857v10.286h3.429V16l2.857-2.857H9.57L14.714 8V0zm9.714 7.429-2.285 2.285H9l-2 2v-2H4.429V1.143h9.142z"/><path d="M11.857 3.143h-1.143V6.57h1.143zm-3.143 0H7.571V6.57h1.143z"/></svg>`,
    kick:   `<svg xmlns="http://www.w3.org/2000/svg" width="16px" height="16px" fill="currentColor" viewBox="0 0 24 24"><path d="M3.98 3h6.01v4h2V5h2V3H20v6.01h-2v2h-2v2h2v2h2v6.01h-6.01v-2h-2v-2h-2v4H3.98z"/></svg>`,
    youtube:`<svg xmlns="http://www.w3.org/2000/svg" width="16px" height="16px" fill="currentColor" viewBox="0 0 16 16"><path d="M8.051 1.999h.089c.822.003 4.987.033 6.11.335a2.01 2.01 0 0 1 1.415 1.42c.101.38.172.883.22 1.402l.01.104.022.26.008.104c.065.914.073 1.77.074 1.957v.075c-.001.194-.01 1.108-.082 2.06l-.008.105-.009.104c-.05.572-.124 1.14-.235 1.558a2.01 2.01 0 0 1-1.415 1.42c-1.16.312-5.569.334-6.18.335h-.142c-.309 0-1.587-.006-2.927-.052l-.17-.006-.087-.004-.171-.007-.171-.007c-1.11-.049-2.167-.128-2.654-.26a2.01 2.01 0 0 1-1.415-1.419c-.111-.417-.185-.986-.235-1.558L.09 9.82l-.008-.104A31 31 0 0 1 0 7.68v-.123c.002-.215.01-.958.064-1.778l.007-.103.003-.052.008-.104.022-.26.01-.104c.048-.519.119-1.023.22-1.402a2.01 2.01 0 0 1 1.415-1.42c.487-.13 1.544-.21 2.654-.26l.17-.007.172-.006.086-.003.171-.007A100 100 0 0 1 7.858 2zM6.4 5.209v4.818l4.157-2.408z"/></svg>`,
    tiktok: `<svg xmlns="http://www.w3.org/2000/svg" width="16px" height="16px" fill="currentColor" viewBox="0 0 16 16"><path d="M9 0h1.98c.144.715.54 1.617 1.235 2.512C12.895 3.389 13.797 4 15 4v2c-1.753 0-3.07-.814-4-1.829V11a5 5 0 1 1-5-5v2a3 3 0 1 0 3 3z"/></svg>`,
};


// Generate a deterministic color from username string.
// Same username always gets the same color across sessions.
const COLORS = ["#FF6B6B","#FFD93D","#6BCB77","#4D96FF","#C77DFF","#FF9F1C","#2EC4B6","#F7B731","#45B7D1","#FF6EB4"];
function nickColor(name) {
    if (!name) return COLORS[0];  
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return COLORS[h % COLORS.length];
}

// Build and insert a chat message element into the DOM.
// Uses data.html (with emote <img> tags) when available, falls back to plain text.
// html field is generated server-side and already XSS-safe.
function addMessage(data) {
    const { platform, username = "unknown", message, html, id } = data;

    const div = document.createElement("div");
    div.className = `msg ${platform}`;

    // Platform icon badge
    const badge = document.createElement("span");
    badge.className = `badge ${platform}`;
    badge.innerHTML = ICONS[platform] || "";

    // Username with deterministic color
    const nick = document.createElement("span");
    nick.className = "username";
    nick.style.color = nickColor(username);
    nick.textContent = username;

    // Message text — use innerHTML only when html field is present (emotes)
    const text = document.createElement("span");
    text.className = "text";
    if (data.html) {
        text.innerHTML = data.html;
    } else {
        text.textContent = message;
    }

    div.append(badge, nick, text);
    chat.appendChild(div);

    // Fade out and remove after 10 seconds
    setTimeout(() => {
        div.classList.add("fade");
        setTimeout(() => div.remove(), 500); // wait for CSS fadeOut animation
    }, 10000);

    // Remove oldest message if limit exceeded
    while (chat.children.length > MAX_MSGS) {
        chat.removeChild(chat.firstChild);
    }
}

// Connect to chat_server.py WebSocket with auto-reconnect on disconnect
let ws;
function connect() {
    ws = new WebSocket(WS_URL);
    ws.onclose = () => setTimeout(connect, 3000); // retry after 3s
    ws.onmessage = (e) => {
        try { addMessage(JSON.parse(e.data)); } catch {}
    };
}

connect();