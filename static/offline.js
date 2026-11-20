const statusLine = document.getElementById('status');
let catalog;
const queueKey = 'ota-offline-queue';
const queue = () => JSON.parse(localStorage.getItem(queueKey) || '[]');
function showQueue() {
  const list = document.getElementById('queue');
  list.replaceChildren();
  queue().forEach(order => {
    const item = document.createElement('li');
    item.textContent = `${order.request_key.slice(0, 8)} · ${order.customer_name} · ${order.username} · awaiting sync`;
    list.append(item);
  });
}
function fillCatalog() {
  if (!catalog) { statusLine.textContent = 'Open this page online once to load your catalog.'; return; }
  document.getElementById('identity').textContent = `Capturing as ${catalog.username}. Prices are confirmed at sync.`;
  for (const [id, rows] of [['customer', catalog.customers], ['sku', catalog.skus]]) {
    const select = document.getElementById(id);
    select.replaceChildren();
    rows.forEach(row => select.add(new Option(row.name, row.id)));
  }
  document.getElementById('capture').disabled = false;
}
// Store before any network request, retaining the same key across lost responses and restarts.
document.getElementById('offline-form').addEventListener('submit', event => {
  event.preventDefault();
  const customer = document.getElementById('customer');
  const quantity = Number(document.getElementById('quantity').value);
  if (!Number.isSafeInteger(quantity) || quantity < 1) return;
  const orders = queue();
  const now = new Date();
  const day = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
  orders.push({request_key: crypto.randomUUID(), user_id: catalog.user_id, username: catalog.username,
    customer: Number(customer.value), customer_name: customer.selectedOptions[0].textContent,
    quantities: {[document.getElementById('sku').value]: quantity}, date: day});
  try {
    localStorage.setItem(queueKey, JSON.stringify(orders));
    statusLine.textContent = 'Saved on this device. Sync when connected.';
    showQueue();
  } catch (_) { statusLine.textContent = 'Device storage failed. Order was not saved.'; }
});
document.getElementById('sync').addEventListener('click', async () => {
  const button = document.getElementById('sync');
  button.disabled = true;
  try {
    const response = await fetch('/offline/catalog/', {cache:'no-store'});
    if (!response.ok || !response.headers.get('content-type').includes('application/json')) throw new Error('Sign in online before syncing.');
    catalog = await response.json();
    localStorage.setItem('ota-offline-catalog', JSON.stringify(catalog));
    fillCatalog();
    for (const order of queue()) {
      if (order.user_id !== catalog.user_id) throw new Error(`Sign in as ${order.username} to sync their queued order.`);
      const result = await fetch('/offline/sync/', {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':catalog.csrf},body:JSON.stringify(order)});
      if (!result.ok) throw new Error(`Sync stopped: ${await result.text()}`);
      localStorage.setItem(queueKey,JSON.stringify(queue().filter(row => row.request_key !== order.request_key)));
      showQueue();
    }
    statusLine.textContent = 'All orders synced. Open Orders to see their status.';
  } catch (error) { statusLine.textContent = error.message; }
  finally { button.disabled = false; }
});
// The worker caches only this public shell and static assets, never authenticated screens.
async function start() {
  if ('serviceWorker' in navigator) await navigator.serviceWorker.register('/service-worker.js');
  try {
    const response = await fetch('/offline/catalog/', {cache:'no-store'});
    if (!response.ok) throw new Error('offline');
    catalog = await response.json();
    localStorage.setItem('ota-offline-catalog',JSON.stringify(catalog));
    statusLine.textContent = 'Catalog ready. Capture here even if connectivity drops.';
  } catch (_) {
    catalog = JSON.parse(localStorage.getItem('ota-offline-catalog') || 'null');
    statusLine.textContent = 'Offline: using the catalog last loaded on this device.';
  }
  fillCatalog(); showQueue();
}
start();
