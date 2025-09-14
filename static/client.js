// ===== client.js =====
const socket = io();

const seen = new Set(); // 중복 렌더링 방지
let username = null;

function qs(id){ return document.getElementById(id); }
const $messages = qs("messages");
const $typing   = qs("typing");
const $input    = qs("input");
const $myname   = document.getElementById("myname");

// ---- IME(한글 조합) 상태 추적 ----
let isComposing = false;
$input.addEventListener("compositionstart", () => { isComposing = true; });
$input.addEventListener("compositionend",   () => { isComposing = false; });

// ---- 메시지 렌더 ----
function appendSystem(msg, ts){
  const li = document.createElement("li");
  li.className = "system";
  li.textContent = `🛈 ${msg} (${new Date(ts).toLocaleTimeString()})`;
  $messages.appendChild(li);
  $messages.scrollTop = $messages.scrollHeight;
}

function appendMessage({id, username, html, ts}){
  if (id && seen.has(id)) return;
  if (id) seen.add(id);

  const li = document.createElement("li");
  const name = document.createElement("strong");
  name.textContent = username + ": ";
  const body = document.createElement("span");
  body.className = "msg-html";
  body.innerHTML = html;
  const time = document.createElement("span");
  time.className = "ts";
  time.textContent = new Date(ts).toLocaleTimeString();

  li.appendChild(name);
  li.appendChild(body);
  li.appendChild(time);
  $messages.appendChild(li);
  $messages.scrollTop = $messages.scrollHeight;
}

// ---- 소켓 핸들러 ----
socket.on("connect", () => {
  socket.emit("join", {});
});

socket.on("set_username", ({username:u}) => {
  username = u;
  if ($myname) $myname.textContent = `내 닉네임: ${username}`;
});

socket.on("history", (items) => {
  $messages.innerHTML = "";
  items.forEach(appendMessage);
});

socket.on("system", ({msg, ts}) => appendSystem(msg, ts));

socket.on("chat_message", (data) => {
  appendMessage(data);
});

socket.on("typing", ({username:u}) => {
  $typing.textContent = `${u} is typing…`;
  setTimeout(() => $typing.textContent = "", 900);
});

// ---- 전송 ----
function sendNow(){
  const text = $input.value.trim();
  if (!text) return;
  socket.emit("chat_message", { text });
  $input.value = "";
  $input.focus();
}

qs("send").addEventListener("click", (e) => {
  e.preventDefault();
  sendNow();
});

// 엔터 전송: IME 조합 중이면 막기 (한글 안전장치)
$input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    if (e.isComposing || isComposing) return; // 한글 조합 중이면 전송 금지
    e.preventDefault();
    sendNow();
  }
});

// 타이핑 표시
$input.addEventListener("input", () => {
  socket.emit("typing", {});
});
