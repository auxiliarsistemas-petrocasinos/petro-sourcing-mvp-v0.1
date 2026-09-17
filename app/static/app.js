const q = (selector) => document.querySelector(selector);

const queryEl = q("#query");
const researchBtn = q("#researchBtn");
const newBtn = q("#newBtn");
const statusCard = q("#statusCard");
const results = q("#results");
const sidebar = q("#sidebar");
const menuBtn = q("#menuBtn");
const closeSidebarBtn = q("#closeSidebarBtn");
const sidebarOverlay = q("#sidebarOverlay");
const queryError = q("#queryError");
const compactNavigation = window.matchMedia("(max-width: 1199px)");

function esc(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function icon(name, className = "") {
  const classAttr = className ? ` class="${esc(className)}"` : "";
  return `<i data-lucide="${esc(name)}"${classAttr} aria-hidden="true"></i>`;
}

function renderIcons() {
  if (window.lucide) {
    window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
  }
}

function humanStatus(value) {
  const labels = {
    confirmado: "Confirmado",
    estimado: "Estimado",
    por_confirmar: "Por confirmar",
    disponible: "Disponible",
    sin_stock: "Sin stock",
    suficiente: "Cantidad suficiente",
    insuficiente: "Cantidad insuficiente",
    requires_review: "Precio por revisar",
  };

  return labels[value] || String(value || "Por confirmar").replaceAll("_", " ");
}

function statusBadge(value) {
  const normalized = String(value || "por_confirmar");
  const cls = normalized.toLowerCase().replaceAll(" ", "_");
  const statusIcon = {
    confirmado: "circle-check",
    disponible: "circle-check",
    suficiente: "circle-check",
    estimado: "clock-3",
    sin_stock: "circle-x",
    insuficiente: "circle-alert",
    requires_review: "triangle-alert",
    por_confirmar: "circle-help",
  }[normalized] || "circle-help";

  return `
    <span class="status status-${esc(cls)}">
      ${icon(statusIcon)}
      <span>${esc(humanStatus(normalized))}</span>
    </span>
  `;
}

function priceReviewBadge(supplier) {
  if (supplier.price_review_status !== "requires_review") {
    return "";
  }

  return statusBadge("requires_review");
}

function isAvailabilityRestricted(supplier) {
  return (
    supplier.availability_status === "sin_stock" ||
    supplier.fulfillment_status === "insuficiente"
  );
}

function availabilityBlock(supplier) {
  const availability = supplier.availability_status || "por_confirmar";
  const fulfillment = supplier.fulfillment_status || "por_confirmar";
  const text = supplier.availability_text || "Por confirmar";
  const restricted = isAvailabilityRestricted(supplier);
  const bothUnconfirmed = (
    availability === "por_confirmar" &&
    fulfillment === "por_confirmar"
  );
  const showAvailabilityText = !(
    bothUnconfirmed && text.trim().toLowerCase() === "por confirmar"
  );
  const availabilityBadges = bothUnconfirmed
    ? `
      <span class="status status-por_confirmar status-combined">
        ${icon("circle-help")}
        <span>Disponibilidad y cantidad por confirmar</span>
      </span>
    `
    : `${statusBadge(availability)}${statusBadge(fulfillment)}`;

  return `
    <div class="availability-block">
      ${showAvailabilityText ? `<div class="availability-text">${esc(text)}</div>` : ""}
      <div class="availability-badges">
        ${availabilityBadges}
      </div>
      ${
        restricted
          ? `<div class="restriction-note">${icon("ban")}<span>No elegible para esta compra</span></div>`
          : ""
      }
    </div>
  `;
}

function money(value, maximumFractionDigits = 0) {
  if (value === null || value === undefined) return "";
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits,
  }).format(value);
}

function validHttpUrl(value) {
  const url = String(value || "").trim();
  return /^https?:\/\//i.test(url) ? url : "";
}

function evidenceLinks(label, sources = []) {
  const links = (sources || [])
    .map((source) => {
      const url = validHttpUrl(source.url);
      if (!url) return "";

      return `
        <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">
          ${icon("external-link")}
          <span>${esc(source.title || url)}</span>
        </a>
      `;
    })
    .filter(Boolean)
    .join("");

  return `
    <div class="evidence-row">
      <strong>${esc(label)}</strong>
      ${links || '<span class="muted">Sin evidencia específica vinculada</span>'}
    </div>
  `;
}

function secondaryPriceDetails(supplier) {
  const parts = [];
  const basis = String(supplier.price_basis || "").trim();
  const baseUnit = String(supplier.price_base_unit || "").trim();
  const hasBasis = basis && basis.toLowerCase() !== "por confirmar";
  const hasBaseUnit = baseUnit && baseUnit.toLowerCase() !== "por confirmar";

  if (hasBasis) {
    const quantity = supplier.price_basis_quantity;
    parts.push(
      `Base: ${esc(basis)}${quantity !== null && quantity !== undefined ? ` × ${esc(quantity)}` : ""}${hasBaseUnit ? ` ${esc(baseUnit)}` : ""}`,
    );
  }

  if (supplier.price_cop_per_unit !== null && supplier.price_cop_per_unit !== undefined) {
    parts.push(
      `${esc(money(supplier.price_cop_per_unit, 2))}${hasBaseUnit ? ` / ${esc(baseUnit)}` : " / unidad"}`,
    );
  }

  return parts.length
    ? `<div class="price-breakdown">${parts.map((part) => `<span>${part}</span>`).join("")}</div>`
    : "";
}

function isCompactUnknown(value, status) {
  return (
    status === "por_confirmar" &&
    String(value || "Por confirmar").trim().toLowerCase() === "por confirmar"
  );
}

function commercialValue(value, status, details = "") {
  if (isCompactUnknown(value, status)) {
    return `<div class="compact-unknown">${statusBadge(status)}</div>`;
  }

  return `
    <strong>${esc(value || "Por confirmar")}</strong>
    ${details}
    ${statusBadge(status)}
  `;
}

function contactValue(type, value) {
  const text = String(value || "Por confirmar").trim() || "Por confirmar";
  if (text.toLowerCase() === "por confirmar") return esc(text);

  if (type === "website") {
    const url = validHttpUrl(text);
    if (url) {
      return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer"><span>${esc(text)}</span>${icon("external-link")}</a>`;
    }
  }

  if (type === "email" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) {
    return `<a href="mailto:${esc(text)}"><span>${esc(text)}</span>${icon("mail")}</a>`;
  }

  if (type === "phone") {
    const dialable = text.replace(/[^\d+]/g, "");
    if (dialable.length >= 7) {
      return `<a href="tel:${esc(dialable)}"><span>${esc(text)}</span>${icon("phone")}</a>`;
    }
  }

  return esc(text);
}

function setLoading(
  on,
  title = "Investigando...",
  text = "Buscando proveedores y contrastando fuentes públicas.",
) {
  researchBtn.disabled = on;
  researchBtn.setAttribute("aria-busy", String(on));
  statusCard.classList.toggle("hidden", !on);
  q("#statusTitle").textContent = title;
  q("#statusText").textContent = text;
}

function render(data) {
  const researchResult = data.result;
  const ranking = data.ranking || [];
  results.classList.remove("hidden");

  q("#reqProduct").textContent = researchResult.product || "Solicitud";
  const requestMeta = [];
  if (researchResult.quantity) requestMeta.push(`Cantidad: ${researchResult.quantity}`);
  requestMeta.push(`Destino: ${researchResult.destination || "Por confirmar"}`);
  q("#reqMeta").textContent = requestMeta.join(" · ");
  q("#specs").innerHTML = (researchResult.required_specifications || [])
    .map((specification) => `<span class="chip">${icon("check")}<span>${esc(specification)}</span></span>`)
    .join("");
  q("#recommendation").textContent = researchResult.recommendation_summary || "";
  q("#sourceCount").textContent = `${ranking.length} proveedor${ranking.length === 1 ? "" : "es"} analizado${ranking.length === 1 ? "" : "s"} · ${data.source_count || 0} fuente${data.source_count === 1 ? "" : "s"}`;

  q("#supplierRows").innerHTML = ranking
    .map((row) => {
      const supplier = row.supplier;
      const certifications = (supplier.certifications || []).length
        ? supplier.certifications.map(esc).join(", ")
        : "Por confirmar";
      const restricted = isAvailabilityRestricted(supplier);
      const location = [supplier.city, supplier.region]
        .filter(Boolean)
        .map(esc)
        .join(", ");

      return `
        <tr class="${restricted ? "supplier-restricted" : ""}">
          <td><span class="rank-number">${esc(row.rank)}</span></td>
          <td>
            <div class="supplier-name">${esc(supplier.supplier_name)}</div>
            <div class="muted table-secondary">${esc(supplier.supplier_type)}</div>
          </td>
          <td>
            <div>${esc(supplier.product_match)}</div>
            ${statusBadge(supplier.product_match_status)}
          </td>
          <td>${availabilityBlock(supplier)}</td>
          <td>${location || "Por confirmar"}</td>
          <td>
            <div class="table-primary-value">${esc(supplier.price_text)}</div>
            ${secondaryPriceDetails(supplier)}
            ${supplier.estimated_total_delivered_cop ? `<div class="table-secondary">${esc(money(supplier.estimated_total_delivered_cop))} total estimado</div>` : ""}
            ${statusBadge(supplier.price_status)}
            ${priceReviewBadge(supplier)}
          </td>
          <td>${esc(supplier.credit_terms)}<br>${statusBadge(supplier.credit_status)}</td>
          <td>${esc(supplier.delivery_time)}<br>${statusBadge(supplier.delivery_status)}</td>
          <td>${certifications}<br>${statusBadge(supplier.certifications_status)}</td>
          <td><span class="score">${esc(row.score)}</span><span class="score-total">/100</span></td>
        </tr>
      `;
    })
    .join("");

  q("#details").innerHTML = ranking
    .map((row) => {
      const supplier = row.supplier;
      const restricted = isAvailabilityRestricted(supplier);
      const sources = (supplier.sources || [])
        .map((source) => {
          const url = validHttpUrl(source.url);
          if (!url) return "";
          return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${icon("external-link")}<span>${esc(source.title || url)}</span></a>`;
        })
        .filter(Boolean)
        .join("") || '<span class="muted">Sin fuente vinculada en la extracción.</span>';
      const location = [supplier.city, supplier.region]
        .filter(Boolean)
        .map(esc)
        .join(", ");
      const certifications = (supplier.certifications || []).length
        ? supplier.certifications.join(", ")
        : "Por confirmar";
      const compactCapacity = isCompactUnknown(
        supplier.capacity,
        supplier.capacity_status,
      );

      return `
        <article class="card supplier-card ${restricted ? "supplier-restricted" : ""}">
          <div class="supplier-card-head">
            <div class="supplier-identity">
              <span class="supplier-rank">#${esc(row.rank)}</span>
              <div>
                <h3>${esc(supplier.supplier_name)}</h3>
                <div class="meta">${location || "Por confirmar"} · ${esc(supplier.supplier_type)}</div>
              </div>
            </div>
            <div class="supplier-score" aria-label="Puntaje ${esc(row.score)} de 100">
              <strong>${esc(row.score)}</strong>
              <span>/100</span>
            </div>
          </div>

          <div class="confidence-line">
            ${icon("shield-check")}
            <span>Confianza ${esc(supplier.confidence)}</span>
            ${statusBadge(supplier.product_match_status)}
          </div>

          <div class="supplier-status-grid">
            <div class="product-match info-panel">
              <strong>Coincidencia con la solicitud</strong>
              <div>${esc(supplier.product_match)}</div>
            </div>

            <div class="availability-detail info-panel">
              <strong>Disponibilidad para esta compra</strong>
              ${availabilityBlock(supplier)}
            </div>
          </div>

          <div class="commercial-grid">
            <div class="commercial-item">
              ${icon("badge-dollar-sign")}
              <span>Precio</span>
              ${commercialValue(
                supplier.price_text,
                supplier.price_status,
                secondaryPriceDetails(supplier),
              )}
              ${priceReviewBadge(supplier)}
            </div>
            <div class="commercial-item">
              ${icon("calendar-clock")}
              <span>Crédito</span>
              ${commercialValue(supplier.credit_terms, supplier.credit_status)}
            </div>
            <div class="commercial-item">
              ${icon("truck")}
              <span>Entrega</span>
              ${commercialValue(supplier.delivery_time, supplier.delivery_status)}
            </div>
            <div class="commercial-item">
              ${icon("award")}
              <span>Certificaciones</span>
              ${commercialValue(certifications, supplier.certifications_status)}
            </div>
          </div>

          <div class="score-grid" aria-label="Puntajes por criterio">
            <div class="metric"><strong>${esc(row.price_score)}</strong><span>Precio</span></div>
            <div class="metric"><strong>${esc(row.credit_score)}</strong><span>Crédito</span></div>
            <div class="metric"><strong>${esc(row.delivery_score)}</strong><span>Entrega</span></div>
            <div class="metric"><strong>${esc(row.certifications_score)}</strong><span>Certif.</span></div>
            <div class="metric"><strong>${esc(row.evidence_score)}</strong><span>Evidencia</span></div>
          </div>

          <div class="evidence-summary">
            ${icon("file-check-2")}
            <div>
              <strong>Resumen de evidencia</strong>
              <p>${esc(supplier.evidence_summary)}</p>
            </div>
          </div>

          <div class="contact">
            <div>${icon("phone")}<span><strong>Teléfono</strong>${contactValue("phone", supplier.phone)}</span></div>
            <div>${icon("mail")}<span><strong>Email</strong>${contactValue("email", supplier.email)}</span></div>
            <div>${icon("globe")}<span><strong>Web</strong>${contactValue("website", supplier.website)}</span></div>
            <div>${icon("boxes")}<span><strong>Capacidad</strong>${compactCapacity ? statusBadge(supplier.capacity_status) : `${esc(supplier.capacity)}${statusBadge(supplier.capacity_status)}`}</span></div>
          </div>

          <details class="field-evidence">
            <summary>
              <span>${icon("link")} Ver evidencia por dato</span>
              ${icon("chevron-down", "details-chevron")}
            </summary>
            <div class="field-evidence-body">
              ${evidenceLinks("Disponibilidad", supplier.availability_sources)}
              ${evidenceLinks("Precio", supplier.price_sources)}
              ${evidenceLinks("Crédito", supplier.credit_sources)}
              ${evidenceLinks("Entrega", supplier.delivery_sources)}
              ${evidenceLinks("Certificaciones", supplier.certifications_sources)}
              ${evidenceLinks("Capacidad", supplier.capacity_sources)}
              ${evidenceLinks("Contacto", supplier.contact_sources)}
            </div>
          </details>

          <div class="sources supplier-sources">
            <p><strong>Fuentes del proveedor</strong></p>
            ${sources}
          </div>
        </article>
      `;
    })
    .join("");

  q("#pending").innerHTML = (researchResult.pending_questions || [])
    .map((question) => `<li>${icon("circle-help")}<span>${esc(question)}</span></li>`)
    .join("");
  q("#globalSources").innerHTML = (data.global_sources || [])
    .map((source) => {
      const url = validHttpUrl(source.url);
      if (!url) return "";
      return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${icon("external-link")}<span>${esc(source.title || url)}</span></a>`;
    })
    .filter(Boolean)
    .join("") || '<span class="muted">No se recuperaron URL explícitas.</span>';
  q("#rawReport").textContent = data.raw_report || "";

  renderIcons();
  window.scrollTo({ top: results.offsetTop - 20, behavior: "smooth" });
}

async function research() {
  const query = queryEl.value.trim();
  if (query.length < 10) {
    queryError.textContent = "Describe la necesidad de compra con un poco más de detalle.";
    queryError.classList.remove("hidden");
    queryEl.setAttribute("aria-invalid", "true");
    queryEl.focus();
    return;
  }

  queryError.textContent = "";
  queryError.classList.add("hidden");
  queryEl.removeAttribute("aria-invalid");

  results.classList.add("hidden");
  setLoading(true);

  try {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "No se pudo completar la investigación.");
    setLoading(false);
    render(body);
    loadHistory();
  } catch (error) {
    setLoading(false);
    window.alert(error.message);
  }
}

async function loadHistory() {
  try {
    const response = await fetch("/api/history");
    if (!response.ok) throw new Error("No se pudo cargar el historial.");
    const rows = await response.json();
    q("#history").innerHTML = rows.length
      ? rows
          .map(
            (row) => `
              <button class="history-item" type="button" data-id="${esc(row.id)}">
                ${icon("file-search")}
                <span class="history-copy">
                  <strong>${esc(row.query)}</strong>
                  <span>${esc(new Date(row.created_at).toLocaleString("es-CO"))}</span>
                </span>
                ${icon("chevron-right", "history-arrow")}
              </button>
            `,
          )
          .join("")
      : '<p class="history-empty">Aún no hay investigaciones.</p>';

    document.querySelectorAll(".history-item").forEach((element) => {
      element.addEventListener("click", async () => {
        const response = await fetch(`/api/history/${element.dataset.id}`);
        if (!response.ok) return;
        const item = await response.json();
        queryEl.value = item.query;
        render(item.result);
        closeSidebar();
      });
    });
    renderIcons();
  } catch {
    q("#history").innerHTML = '<p class="history-empty">Historial no disponible.</p>';
  }
}

function openSidebar() {
  sidebar.classList.add("is-open");
  sidebarOverlay.classList.add("is-visible");
  document.body.classList.add("sidebar-open");
  menuBtn.setAttribute("aria-expanded", "true");
  closeSidebarBtn.focus();
}

function closeSidebar() {
  sidebar.classList.remove("is-open");
  sidebarOverlay.classList.remove("is-visible");
  document.body.classList.remove("sidebar-open");
  menuBtn.setAttribute("aria-expanded", "false");
}

researchBtn.addEventListener("click", research);
queryEl.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") research();
});
queryEl.addEventListener("input", () => {
  if (queryEl.value.trim().length >= 10) {
    queryError.textContent = "";
    queryError.classList.add("hidden");
    queryEl.removeAttribute("aria-invalid");
  }
});
newBtn.addEventListener("click", () => {
  queryEl.value = "";
  queryError.textContent = "";
  queryError.classList.add("hidden");
  queryEl.removeAttribute("aria-invalid");
  results.classList.add("hidden");
  closeSidebar();
  queryEl.focus();
  q("#researchComposer").scrollIntoView({ behavior: "smooth", block: "start" });
});
menuBtn.addEventListener("click", openSidebar);
closeSidebarBtn.addEventListener("click", () => {
  closeSidebar();
  menuBtn.focus();
});
sidebarOverlay.addEventListener("click", closeSidebar);
document.querySelectorAll(".primary-nav a, .brand").forEach((link) => {
  link.addEventListener("click", () => {
    if (compactNavigation.matches) closeSidebar();
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && sidebar.classList.contains("is-open")) {
    closeSidebar();
    menuBtn.focus();
  }
});
compactNavigation.addEventListener("change", (event) => {
  if (!event.matches) closeSidebar();
});

renderIcons();
loadHistory();
