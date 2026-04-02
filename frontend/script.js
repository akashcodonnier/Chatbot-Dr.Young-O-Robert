// State Management
let conversationId = "conv_" + Date.now();
const chatArea = document.getElementById("chatArea");
const questionInput = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");
const themeToggle = document.getElementById("theme-toggle");
const themeIcon = document.getElementById("theme-icon");
const statusPill = document.getElementById("status-pill");

// Local Storage for Theme
const savedTheme = localStorage.getItem("chatbot-theme") || "light";
document.documentElement.setAttribute("data-theme", savedTheme);
updateThemeIcon(savedTheme);

function updateThemeIcon(theme) {
    if (theme === "dark") {
        themeIcon.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`;
    } else {
        themeIcon.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
}

themeToggle.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme");
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("chatbot-theme", newTheme);
    updateThemeIcon(newTheme);
});

// UI Helpers
function getTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function updateStatus(text, isThinking = false) {
    const dot = statusPill.querySelector(".status-dot");
    const label = statusPill.querySelector(".status-label");
    
    label.textContent = text;
    if (isThinking) {
        statusPill.style.color = "var(--accent-primary)";
        dot.style.background = "var(--accent-primary)";
    } else {
        statusPill.style.color = "#10b981";
        dot.style.background = "#10b981";
    }
}

function formatBotResponse(text) {
    // Basic formatting
    text = text.replace(/Zeolité/g, "Zeolite");
    text = text.replace(/pH/gi, "pH");
    
    // Formatting links
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    let htmlResult = "";

    for (let i = 0; i < parts.length; i++) {
        if (parts[i].match(urlRegex)) {
            let url = parts[i];
            const trailingPunct = /[.,!?;:]+$/;
            const match = url.match(trailingPunct);
            let suffix = "";
            if (match) {
                suffix = match[0];
                url = url.replace(trailingPunct, '');
            }
            htmlResult += `<a href="${url}" target="_blank" class="chat-link" style="color: var(--accent-primary); text-decoration: none; font-weight: 500;">${url}</a>${suffix}`;
        } else {
            let segment = parts[i];
            segment = segment.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            htmlResult += segment.replace(/\n/g, '<br>');
        }
    }
    return htmlResult;
}

// Chat Logic
function addMessage(text, sender) {
    // Remove welcome screen on first message
    const welcome = document.getElementById("welcome");
    if (welcome) welcome.style.display = "none";

    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${sender}`;
    
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = sender === "user" ? "U" : "M";
    
    const content = document.createElement("div");
    content.className = "message-content";
    
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (sender === "user") {
        bubble.textContent = text;
    } else {
        bubble.innerHTML = formatBotResponse(text);
    }
    
    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = getTime();
    
    content.appendChild(bubble);
    content.appendChild(time);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    
    chatArea.appendChild(messageDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
    
    return bubble;
}

function showTyping() {
    const typingDiv = document.createElement("div");
    typingDiv.className = "message bot";
    typingDiv.id = "typing-indicator";
    
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "M";
    
    const content = document.createElement("div");
    content.className = "message-content";
    
    const bubble = document.createElement("div");
    bubble.className = "bubble typing";
    bubble.innerHTML = "<span></span><span></span><span></span>";
    
    content.appendChild(bubble);
    typingDiv.appendChild(avatar);
    typingDiv.appendChild(content);
    
    chatArea.appendChild(typingDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
}

function removeTyping() {
    const typing = document.getElementById("typing-indicator");
    if (typing) typing.remove();
}

async function sendMessage() {
    const question = questionInput.value.trim();
    if (!question) return;

    addMessage(question, "user");
    questionInput.value = "";
    questionInput.style.height = 'auto'; // Reset height
    sendBtn.disabled = true;
    questionInput.disabled = true;

    showTyping();
    updateStatus("Thinking...", true);

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                conversation_id: conversationId
            })
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let accumulatedText = "";
        let botBubble = null;

        while (true) {
            const { value, done } = await reader.read();
            const chunk = decoder.decode(value || new Uint8Array(), { stream: !done });
            accumulatedText += chunk;

            if (!botBubble && accumulatedText.trim()) {
                removeTyping();
                botBubble = addMessage("", "bot");
            }

            if (botBubble) {
                botBubble.innerHTML = formatBotResponse(accumulatedText);
                chatArea.scrollTop = chatArea.scrollHeight;
            }

            if (done) break;
        }
        updateStatus("Online");

    } catch (err) {
        removeTyping();
        updateStatus("Error", false);
        const errorBubble = addMessage(`Error: ${err.message}`, "bot");
        errorBubble.style.color = "#dc2626";
    }

    sendBtn.disabled = false;
    questionInput.disabled = false;
    questionInput.focus();
}

// Event Listeners
sendBtn.addEventListener("click", sendMessage);
questionInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Auto-expand textarea
questionInput.addEventListener('input', () => {
    questionInput.style.height = 'auto';
    questionInput.style.height = (questionInput.scrollHeight) + 'px';
});

// Suggestions
window.askSuggestion = (text) => {
    questionInput.value = text;
    sendMessage();
};

// Voice Input (Simplified)
const micBtn = document.getElementById("mic-btn");
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        micBtn.style.color = "#dc2626";
        updateStatus("Listening...");
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        questionInput.value = transcript;
        sendMessage();
    };

    recognition.onend = () => {
        micBtn.style.color = "var(--text-secondary)";
        updateStatus("Online");
    };

    micBtn.addEventListener("click", () => {
        recognition.start();
    });
} else {
    micBtn.style.display = "none";
}
