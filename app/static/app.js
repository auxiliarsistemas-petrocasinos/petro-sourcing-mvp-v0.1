const q = (s) => document.querySelector(s);

const queryEl = q("#query");
const researchBtn = q("#researchBtn");
const newBtn = q("#newBtn");
const statusCard = q("#statusCard");
const results = q("#results");

function esc(value="") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function statusBadge(value) {
  const cls = String(value || "por_confirmar").replaceAll(" ", "_");
  return `<span class="status status-${cls}">${esc(value || "por confirmar")}</span>`;
}

function money(v) {
  if (v === null || v === undefined) return "";
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(v);
}

function evidenceLinks(label, sources=[]) {
  const links = (sources || []).map(src => {
    const url = String(src.url || "").trim();

    if (!/^https?:\/\//i.test(url)) return "";

    return `
      <a href="${esc(url)}"
         target="_blank"
         rel="noopener noreferrer">
        ${esc(src.title || url)}
      </a>
    `;
  }).filter(Boolean).join("");

  return `
    <div class="evidence-row">
      <strong>${esc(label)}</strong>
      ${
        links ||
        '<span class="muted">Sin evidencia específica vinculada</span>'
      }
    </div>
  `;
}


function setLoading(on, title="Investigando...", text="Buscando proveedores y contrastando fuentes públicas.") {
  researchBtn.disabled = on;
  statusCard.classList.toggle("hidden", !on);
  q("#statusTitle").textContent = title;
  q("#statusText").textContent = text;
}

function render(data) {
  const r = data.result;
  results.classList.remove("hidden");

  q("#reqProduct").textContent = r.product || "Solicitud";
  q("#reqMeta").textContent = `${r.quantity || ""} · Destino: ${r.destination || "Por confirmar"}`;
  q("#specs").innerHTML = (r.required_specifications || []).map(x => `<span class="chip">${esc(x)}</span>`).join("");
  q("#recommendation").textContent = r.recommendation_summary || "";
  q("#sourceCount").textContent = `${data.source_count || 0} fuentes web citadas`;

  q("#supplierRows").innerHTML = (data.ranking || []).map(row => {
    const s = row.supplier;
    const certs = (s.certifications || []).length ? s.certifications.join(", ") : "Por confirmar";
    return `
      <tr>
        <td><strong>${row.rank}</strong></td>
        <td>
          <div class="supplier-name">${esc(s.supplier_name)}</div>
          <div class="muted">${esc(s.supplier_type)}</div>
        </td>
        <td>
          <div>${esc(s.product_match)}</div>
          ${statusBadge(s.product_match_status)}
        </td>
        <td>${esc(s.city)}, ${esc(s.region)}</td>
        <td>
          ${esc(s.price_text)}
          ${s.estimated_total_delivered_cop ? `<div>${money(s.estimated_total_delivered_cop)} total estimado</div>` : ""}
          ${statusBadge(s.price_status)}
        </td>
        <td>${esc(s.credit_terms)}<br>${statusBadge(s.credit_status)}</td>
        <td>${esc(s.delivery_time)}<br>${statusBadge(s.delivery_status)}</td>
        <td>${esc(certs)}<br>${statusBadge(s.certifications_status)}</td>
        <td><span class="score">${row.score}</span>/100</td>
      </tr>
    `;
  }).join("");

  q("#details").innerHTML = (data.ranking || []).map(row => {
    const s = row.supplier;
    const sources = (s.sources || []).map(src =>
      `<a href="${esc(src.url)}" target="_blank" rel="noopener noreferrer">${esc(src.title || src.url)}</a>`
    ).join("") || `<span class="muted">Sin fuente vinculada en la extracción.</span>`;

    return `
      <article class="card supplier-card">
        <span class="eyebrow">#${row.rank} · ${row.score}/100 · Confianza ${esc(s.confidence)}</span>
        <h3>${esc(s.supplier_name)}</h3>
        <div class="meta">${esc(s.city)}, ${esc(s.region)} · ${esc(s.supplier_type)}</div>

        <div class="product-match">
          <strong>Coincidencia con la solicitud</strong>
          <div>${esc(s.product_match)}</div>
          ${statusBadge(s.product_match_status)}
        </div>

        <p>${esc(s.evidence_summary)}</p>

        <div class="score-grid">
          <div class="metric"><strong>${row.price_score}</strong><span>Precio</span></div>
          <div class="metric"><strong>${row.credit_score}</strong><span>Crédito</span></div>
          <div class="metric"><strong>${row.delivery_score}</strong><span>Entrega</span></div>
          <div class="metric"><strong>${row.certifications_score}</strong><span>Certif.</span></div>
          <div class="metric"><strong>${row.evidence_score}</strong><span>Evidencia</span></div>
        </div>

        <div class="contact">
          <div><strong>Teléfono</strong><br>${esc(s.phone)}</div>
          <div><strong>Email</strong><br>${esc(s.email)}</div>
          <div><strong>Web</strong><br>${esc(s.website)}</div>
          <div><strong>Capacidad</strong><br>${esc(s.capacity)}<br>${statusBadge(s.capacity_status)}</div>
        </div>

        <details class="field-evidence">
          <summary>Ver evidencia por dato</summary>
          <div class="field-evidence-body">
            ${evidenceLinks("Precio", s.price_sources)}
            ${evidenceLinks("Crédito", s.credit_sources)}
            ${evidenceLinks("Entrega", s.delivery_sources)}
            ${evidenceLinks(
              "Certificaciones",
              s.certifications_sources
            )}
            ${evidenceLinks("Capacidad", s.capacity_sources)}
            ${evidenceLinks("Contacto", s.contact_sources)}
          </div>
        </details>

        <div class="sources">
          <p><strong>Fuentes del proveedor</strong></p>
          ${sources}
        </div>
      </article>
    `;
  }).join("");

  q("#pending").innerHTML = (r.pending_questions || []).map(x => `<li>${esc(x)}</li>`).join("");
  q("#globalSources").innerHTML = (data.global_sources || []).map(src =>
    `<a href="${esc(src.url)}" target="_blank" rel="noopener noreferrer">${esc(src.title || src.url)}</a>`
  ).join("") || `<span class="muted">No se recuperaron URL explícitas.</span>`;
  q("#rawReport").textContent = data.raw_report || "";

  window.scrollTo({ top: results.offsetTop - 20, behavior: "smooth" });
}

async function research() {
  const query = queryEl.value.trim();
  if (query.length < 10) {
    alert("Describe la necesidad de compra con un poco más de detalle.");
    return;
  }

  results.classList.add("hidden");
  setLoading(true);

  try {
    const res = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query })
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || "No se pudo completar la investigación.");
    setLoading(false);
    render(body);
    loadHistory();
  } catch (err) {
    setLoading(false);
    alert(err.message);
  }
}

async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const rows = await res.json();
    q("#history").innerHTML = rows.map(row => `
      <div class="history-item" data-id="${row.id}">
        <strong>${esc(row.query)}</strong>
        <span>${new Date(row.created_at).toLocaleString("es-CO")}</span>
      </div>
    `).join("");

    document.querySelectorAll(".history-item").forEach(el => {
      el.addEventListener("click", async () => {
        const r = await fetch(`/api/history/${el.dataset.id}`);
        const item = await r.json();
        queryEl.value = item.query;
        render(item.result);
      });
    });
  } catch {}
}

researchBtn.addEventListener("click", research);
queryEl.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") research();
});
newBtn.addEventListener("click", () => {
  queryEl.value = "";
  results.classList.add("hidden");
  queryEl.focus();
});

loadHistory();
