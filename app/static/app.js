// app.js — Logica dell'area cassa (JS vanilla, nessun framework).
// Gestisce: caricamento prodotti, griglia per categoria, carrello in memoria,
// calcolo totale live e creazione/stampa ordine.

"use strict";

// ---------------------------------------------------------------------------
// Stato in memoria
// ---------------------------------------------------------------------------

// Carrello: mappa product_id -> { product, qty }
const cart = new Map();

// Cache dei prodotti caricati dal server.
let products = [];

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

// Converte centesimi interi in stringa euro con 2 decimali, es. 400 -> "4.00 €".
function formatEuro(cents) {
  return (cents / 100).toFixed(2) + " €";
}

// Mostra un breve messaggio temporaneo (toast) in basso.
function showToast(message, isError) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = "toast show" + (isError ? " error" : "");
  // Nasconde il toast dopo qualche secondo.
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(function () {
    toast.className = "toast";
  }, 3500);
}

// ---------------------------------------------------------------------------
// Caricamento e rendering prodotti
// ---------------------------------------------------------------------------

// Carica le impostazioni per personalizzare intestazione.
async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    if (!res.ok) return;
    const s = await res.json();
    if (s.event_name) {
      document.getElementById("event-title").textContent = s.event_name;
      document.title = "Cassa - " + s.event_name;
    }
    if (s.association_name) {
      document.getElementById("association-name").textContent = s.association_name;
    }
  } catch (err) {
    // Le impostazioni sono opzionali per la cassa: ignoriamo eventuali errori.
  }
}

// Carica i prodotti dal server e li mostra.
async function loadProducts() {
  const container = document.getElementById("products");
  try {
    const res = await fetch("/api/products");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const all = await res.json();
    // Solo prodotti attivi, ordinati per sort_order (poi per nome a parità).
    products = all
      .filter(function (p) { return p.active; })
      .sort(function (a, b) {
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.name.localeCompare(b.name);
      });
    renderProducts();
  } catch (err) {
    container.innerHTML =
      '<p class="error-box">Impossibile caricare i prodotti. ' +
      "Controlla la connessione al server.</p>";
  }
}

// Raggruppa i prodotti per categoria e costruisce la griglia di pulsanti.
function renderProducts() {
  const container = document.getElementById("products");
  container.innerHTML = "";

  if (products.length === 0) {
    container.innerHTML = '<p class="loading">Nessun prodotto disponibile.</p>';
    return;
  }

  // Raggruppa mantenendo l'ordine di prima apparizione delle categorie.
  const groups = new Map();
  for (const p of products) {
    const cat = p.category || "Generale";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(p);
  }

  for (const [category, items] of groups) {
    const section = document.createElement("section");
    section.className = "category";

    const heading = document.createElement("h3");
    heading.className = "category-title";
    heading.textContent = category;
    section.appendChild(heading);

    const grid = document.createElement("div");
    grid.className = "product-grid";

    for (const p of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "product-btn";
      btn.innerHTML =
        '<span class="product-name"></span>' +
        '<span class="product-price">' + formatEuro(p.price_cents) + "</span>";
      // Inserisce il nome come testo (evita problemi con caratteri speciali).
      btn.querySelector(".product-name").textContent = p.name;
      btn.addEventListener("click", function () { addToCart(p); });
      grid.appendChild(btn);
    }

    section.appendChild(grid);
    container.appendChild(section);
  }
}

// ---------------------------------------------------------------------------
// Gestione carrello
// ---------------------------------------------------------------------------

// Aggiunge un prodotto al carrello (o ne incrementa la quantità).
function addToCart(product) {
  const entry = cart.get(product.id);
  if (entry) {
    entry.qty += 1;
  } else {
    cart.set(product.id, { product: product, qty: 1 });
  }
  renderCart();
}

// Modifica la quantità di una riga; se arriva a 0 la rimuove.
function changeQty(productId, delta) {
  const entry = cart.get(productId);
  if (!entry) return;
  entry.qty += delta;
  if (entry.qty <= 0) {
    cart.delete(productId);
  }
  renderCart();
}

// Calcola il totale del carrello in centesimi.
function cartTotalCents() {
  let total = 0;
  for (const { product, qty } of cart.values()) {
    total += product.price_cents * qty;
  }
  return total;
}

// Ridisegna le righe del carrello e il totale.
function renderCart() {
  const linesEl = document.getElementById("cart-lines");
  linesEl.innerHTML = "";

  if (cart.size === 0) {
    linesEl.innerHTML = '<p class="cart-empty">Nessun prodotto selezionato.</p>';
  } else {
    for (const [productId, { product, qty }] of cart) {
      const line = document.createElement("div");
      line.className = "cart-line";

      const name = document.createElement("div");
      name.className = "cart-line-name";
      name.textContent = product.name;

      const controls = document.createElement("div");
      controls.className = "cart-qty";

      const minus = document.createElement("button");
      minus.type = "button";
      minus.className = "qty-btn";
      minus.textContent = "−"; // segno meno
      minus.addEventListener("click", function () { changeQty(productId, -1); });

      const qtyVal = document.createElement("span");
      qtyVal.className = "qty-val";
      qtyVal.textContent = qty;

      const plus = document.createElement("button");
      plus.type = "button";
      plus.className = "qty-btn";
      plus.textContent = "+";
      plus.addEventListener("click", function () { changeQty(productId, 1); });

      controls.appendChild(minus);
      controls.appendChild(qtyVal);
      controls.appendChild(plus);

      const lineTotal = document.createElement("div");
      lineTotal.className = "cart-line-total";
      lineTotal.textContent = formatEuro(product.price_cents * qty);

      line.appendChild(name);
      line.appendChild(controls);
      line.appendChild(lineTotal);
      linesEl.appendChild(line);
    }
  }

  document.getElementById("cart-total-value").textContent =
    formatEuro(cartTotalCents());
}

// Svuota il carrello.
function clearCart() {
  cart.clear();
  renderCart();
}

// ---------------------------------------------------------------------------
// Creazione e stampa ordine
// ---------------------------------------------------------------------------

async function submitOrder() {
  if (cart.size === 0) {
    showToast("Il carrello e' vuoto.", true);
    return;
  }

  const btn = document.getElementById("btn-print");
  btn.disabled = true;

  // Costruisce gli items per l'API (solo product_id e quantity).
  const items = [];
  for (const [productId, { qty }] of cart) {
    items.push({ product_id: productId, quantity: qty });
  }

  let order;
  try {
    // 1) Crea l'ordine: i totali sono calcolati lato server.
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: items, note: null }),
    });
    if (!res.ok) {
      const detail = await readError(res);
      throw new Error(detail || "Errore nella creazione dell'ordine.");
    }
    order = await res.json();
  } catch (err) {
    // Se l'ordine non viene creato, il carrello resta intatto per riprovare.
    showToast("Errore: " + err.message, true);
    btn.disabled = false;
    return;
  }

  // 2) Tenta la stampa. L'ordine e' gia' salvato: se la stampa fallisce
  //    avvisiamo ma svuotiamo comunque il carrello (vendita registrata).
  try {
    const printRes = await fetch("/api/orders/" + order.id + "/print", {
      method: "POST",
    });
    if (!printRes.ok) {
      const detail = await readError(printRes);
      throw new Error(detail || "stampa non riuscita");
    }
    const result = await printRes.json();
    if (result.ok) {
      showToast("Ordine #" + order.id + " stampato. Totale " +
        formatEuro(order.total_cents), false);
    } else {
      showToast("Ordine #" + order.id + " salvato ma stampa fallita (" +
        (result.detail || result.mode) + "). Puoi ristampare dalla gestione.", true);
    }
  } catch (err) {
    showToast("Ordine #" + order.id + " salvato, ma la stampa non e' riuscita: " +
      err.message + ". L'ordine NON e' perso.", true);
  }

  // 3) In ogni caso l'ordine e' stato salvato: svuotiamo il carrello.
  clearCart();
  btn.disabled = false;
}

// Estrae un messaggio di errore leggibile da una risposta non ok.
async function readError(res) {
  try {
    const data = await res.json();
    if (data && data.detail) {
      // FastAPI puo' restituire detail come stringa o lista di errori.
      if (typeof data.detail === "string") return data.detail;
      return JSON.stringify(data.detail);
    }
  } catch (e) {
    // corpo non JSON
  }
  return "HTTP " + res.status;
}

// ---------------------------------------------------------------------------
// Annulla ordine
// ---------------------------------------------------------------------------

function cancelOrder() {
  if (cart.size === 0) return;
  if (confirm("Annullare l'ordine corrente e svuotare il carrello?")) {
    clearCart();
    showToast("Ordine annullato.", false);
  }
}

// ---------------------------------------------------------------------------
// Avvio
// ---------------------------------------------------------------------------

document.getElementById("btn-print").addEventListener("click", submitOrder);
document.getElementById("btn-cancel").addEventListener("click", cancelOrder);

loadSettings();
loadProducts();
renderCart();
