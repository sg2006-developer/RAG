// static/chat.js
const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("message");
const sendBtn = document.getElementById("send-btn");

function addUserMessage(text){
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerText = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

function addBotMessage(text, sources){
  const el = document.createElement("div");
  el.className = "msg bot";
  // allow line breaks
  const main = document.createElement("div");
  main.innerHTML = sanitize(text).replace(/\n/g,"<br/>");
  el.appendChild(main);

  if(Array.isArray(sources) && sources.length){
    const chips = document.createElement("div");
    chips.className = "sources";
    sources.forEach(s => {
      const c = document.createElement("div");
      c.className = "source";
      // clickable link if available
      if(s.video_link){
        c.innerHTML = `<strong>${escapeHtml(s.title)}</strong> <a href="${escapeHtml(s.video_link)}" target="_blank">▶</a> <span style="opacity:.9"> ${formatTime(s.start)}</span>`;
      } else {
        c.innerHTML = `<strong>${escapeHtml(s.title)}</strong> <span style="opacity:.9"> ${formatTime(s.start)}</span>`;
      }
      chips.appendChild(c);
    });
    el.appendChild(chips);
  }

  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

function addTypingIndicator(){
  const el = document.createElement("div");
  el.className = "msg bot typing";
  el.id = "typing-indicator";
  el.innerHTML = `<div class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>`;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

function removeTypingIndicator(){
  const t = document.getElementById("typing-indicator");
  if(t) t.remove();
}

function formatTime(sec){
  sec = Math.floor(sec||0);
  const h = Math.floor(sec/3600);
  const m = Math.floor((sec%3600)/60);
  const s = sec%60;
  if(h>0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${m}:${String(s).padStart(2,'0')}`;
}

function sanitize(str){
  if(!str) return "";
  return String(str).replace(/[&<>"']/g, function(m){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]; });
}

function escapeHtml(s){ return sanitize(s); }

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if(!text) return;
  addUserMessage(text);
  input.value = "";
  sendBtn.disabled = true;
  addTypingIndicator();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({message: text})
    });
    const json = await res.json();
    removeTypingIndicator();
    sendBtn.disabled = false;
    if(json.error){
      addBotMessage("Error: " + json.error, []);
      return;
    }
    addBotMessage(json.answer, json.sources || []);
  } catch (err) {
    removeTypingIndicator();
    sendBtn.disabled = false;
    addBotMessage("Network error: " + err.message, []);
  }
});
