const galleryEl = document.getElementById("gallery");
const promptEl = document.getElementById("prompt");
const presetEl = document.getElementById("preset");
const countEl = document.getElementById("count");
const generateBtn = document.getElementById("generateBtn");
const suggestBtn = document.getElementById("suggestBtn");
const suggestionsEl = document.getElementById("suggestions");
const exportBtn = document.getElementById("exportBtn");
const exportZipBtn = document.getElementById("exportZipBtn");
const selectedCountEl = document.getElementById("selectedCount");

const selected = new Set();
let presetsCache = {};

async function loadPresets() {
  presetsCache = await fetch("/api/presets").then((r) => r.json());
  presetEl.innerHTML = Object.entries(presetsCache)
    .map(([key, p]) => `<option value="${key}">${p.label}</option>`)
    .join("");
}

async function loadImages() {
  const images = await fetch("/api/images").then((r) => r.json());
  render(images);
}

function updateSelectedCount() {
  selectedCountEl.textContent = `${selected.size}개 선택됨`;
}

function statusLabel(status) {
  const map = {
    generated: "생성됨",
    bg_removed: "배경 제거됨",
    upscaled: "업스케일됨",
    vectorized: "벡터화됨",
    resized: "크기 조절됨",
    optimized: "최적화됨",
    ready: "메타데이터 완료",
  };
  return map[status] || status;
}

function render(images) {
  galleryEl.innerHTML = images.map(cardHtml).join("");
  images.forEach((img) => {
    const card = document.getElementById(`card-${img.id}`);
    card.querySelector(".select-box").addEventListener("change", (e) => {
      if (e.target.checked) selected.add(img.id);
      else selected.delete(img.id);
      updateSelectedCount();
    });
    card.querySelector(".btn-bg")?.addEventListener("click", () => runAction(img.id, "remove-background"));
    card.querySelector(".btn-upscale")?.addEventListener("click", () => runAction(img.id, "upscale", { mode: "crisp" }));
    card.querySelector(".btn-vectorize")?.addEventListener("click", () => runAction(img.id, "vectorize"));
    card.querySelector(".btn-resize")?.addEventListener("click", () => runAction(img.id, "resize", { long_edge: 2000 }));
    card.querySelector(".btn-optimize")?.addEventListener("click", () => runAction(img.id, "optimize"));
    card.querySelector(".btn-metadata")?.addEventListener("click", () => runAction(img.id, "metadata"));
  });
}

function cardHtml(img) {
  const src = `/images/${img.filename}`;
  return `
  <div class="card" id="card-${img.id}">
    <img src="${src}" loading="lazy" />
    <div class="body">
      <label class="select-row">
        <input type="checkbox" class="select-box" ${selected.has(img.id) ? "checked" : ""} />
        <span class="status">${statusLabel(img.status)}</span>
      </label>
      <div class="prompt" title="${img.prompt || ""}">${img.prompt || ""}</div>
      ${img.title ? `<div class="meta"><b>제목:</b> ${img.title}</div>` : ""}
      ${img.keywords ? `<div class="meta"><b>키워드(EN):</b> ${img.keywords}</div>` : ""}
      ${img.keywords_ko ? `<div class="meta"><b>키워드(KR):</b> ${img.keywords_ko}</div>` : ""}
      ${img.stock_category_id ? `<div class="meta"><b>카테고리:</b> #${img.stock_category_id}</div>` : ""}
      <div class="actions">
        ${!img.is_vector ? `<button class="btn-bg">배경제거</button>` : ""}
        ${!img.is_vector ? `<button class="btn-upscale">업스케일</button>` : ""}
        ${!img.is_vector ? `<button class="btn-vectorize">벡터화</button>` : ""}
        ${!img.is_vector ? `<button class="btn-resize">크기조절</button>` : ""}
        ${!img.is_vector ? `<button class="btn-optimize">최적화</button>` : ""}
        ${!img.is_vector ? `<button class="btn-metadata">메타데이터</button>` : ""}
        <a class="btn-download" href="${src}" download="${img.filename}">다운로드</a>
      </div>
    </div>
  </div>`;
}

async function runAction(id, action, body) {
  const btn = event?.target;
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/images/${id}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`실패: ${err.detail || res.statusText}`);
      return;
    }
    const result = await res.json();
    if (action === "optimize" && result.size_before) {
      const before = (result.size_before / 1024).toFixed(0);
      const after = (result.size_after / 1024).toFixed(0);
      alert(`파일 크기: ${before}KB → ${after}KB`);
    }
    await loadImages();
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderSuggestions(topics) {
  suggestionsEl.innerHTML = topics
    .map((t, i) => {
      const presetOptions = Object.entries(presetsCache)
        .map(([key, p]) => `<option value="${key}">${p.label}</option>`)
        .join("");
      const scenes = (t.scenes || [])
        .map((s, j) => `<button class="scene" data-i="${i}" data-j="${j}">${s}</button>`)
        .join("");
      return `
      <div class="suggest-row">
        <div class="suggest-rank">${i + 1}</div>
        <div class="suggest-body">
          <div class="suggest-topic">${t.topic}</div>
          <button class="suggest-toggle" data-i="${i}">장면 설명 ${(t.scenes || []).length}개 펼쳐보기</button>
          <div class="suggest-scenes" id="scenes-${i}">${scenes}</div>
        </div>
        <div class="suggest-make">
          <select data-i="${i}">
            <option value="">제작하기</option>
            ${presetOptions}
          </select>
        </div>
      </div>`;
    })
    .join("");

  suggestionsEl.querySelectorAll(".suggest-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById(`scenes-${btn.dataset.i}`).classList.toggle("open");
    });
  });
  suggestionsEl.querySelectorAll(".scene").forEach((btn) => {
    btn.addEventListener("click", () => {
      promptEl.value = btn.textContent;
      promptEl.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
  suggestionsEl.querySelectorAll(".suggest-make").forEach((wrap) => {
    const select = wrap.querySelector("select");
    select.addEventListener("change", () => {
      if (!select.value) return;
      const i = Number(select.dataset.i);
      presetEl.value = select.value;
      promptEl.value = (topics[i].scenes || [])[0] || topics[i].topic;
      select.value = "";
      promptEl.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

document.querySelectorAll(".nav-link[data-preset]").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    presetEl.value = link.dataset.preset;
    promptEl.focus();
    promptEl.scrollIntoView({ behavior: "smooth", block: "center" });
  });
});

async function fetchSuggestions() {
  suggestBtn.disabled = true;
  suggestBtn.textContent = "추천 불러오는 중...";
  try {
    const res = await fetch("/api/suggest-topics");
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`추천 실패: ${err.detail || res.statusText}`);
      return;
    }
    const topics = await res.json();
    renderSuggestions(topics);
    suggestionsEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    suggestBtn.disabled = false;
    suggestBtn.textContent = "지금 잘 팔리는 주제 추천";
  }
}

suggestBtn.addEventListener("click", fetchSuggestions);

document.querySelector('a[href="#suggestions-section"]').addEventListener("click", (e) => {
  e.preventDefault();
  fetchSuggestions();
});

generateBtn.addEventListener("click", async () => {
  const prompt = promptEl.value.trim();
  if (!prompt) return alert("프롬프트를 입력하세요");
  generateBtn.disabled = true;
  generateBtn.textContent = "생성 중...";
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        preset: presetEl.value,
        n: Number(countEl.value),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`생성 실패: ${err.detail || res.statusText}`);
      return;
    }
    await loadImages();
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "생성";
  }
});

exportBtn.addEventListener("click", () => {
  if (selected.size === 0) return alert("내보낼 이미지를 선택하세요");
  fetch("/api/export-csv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: Array.from(selected) }),
  })
    .then((res) => res.blob())
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "adobe_stock_metadata.csv";
      a.click();
      URL.revokeObjectURL(url);
    });
});

exportZipBtn.addEventListener("click", () => {
  if (selected.size === 0) return alert("내보낼 이미지를 선택하세요");
  fetch("/api/export-zip", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: Array.from(selected) }),
  })
    .then((res) => res.blob())
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "stock-images.zip";
      a.click();
      URL.revokeObjectURL(url);
    });
});

loadPresets();
loadImages();
