import React, { useEffect, useState, useRef } from "react";
type Props = { catalog?: any; token?: string };
const queueKey = "ota-react-orders-v1";

// Persist request keys before attempting sync; retain failed and other-user orders.
export function Offline({ catalog, token }: Props) {
  const [saved] = useState(
    () =>
      catalog ||
      JSON.parse(localStorage.getItem("ota-react-catalog") || "null"),
  );
  const [queue, setQueue] = useState<any[]>(() =>
    JSON.parse(localStorage.getItem(queueKey) || "[]"),
  );
  const [message, setMessage] = useState(
    "Orders stay on this device until synced.",
  );
  const [busy, setBusy] = useState(false);
  const syncing = useRef(false);
  async function sync() {
    if (
      !token ||
      !catalog ||
      syncing.current ||
      !navigator.onLine ||
      JSON.parse(localStorage.getItem(queueKey) || "[]").length === 0
    )
      return;
    syncing.current = true;
    setBusy(true);
    try {
      for (const order of JSON.parse(localStorage.getItem(queueKey) || "[]")) {
        if (order.user_id !== catalog.user_id)
          throw new Error("Sign in as the user who captured the queued order.");
        const response = await fetch("/api/workspace/offline/sync", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(order),
        });
        if (!response.ok)
          throw new Error("Sync stopped: " + (await response.text()));
        const remaining = JSON.parse(
          localStorage.getItem(queueKey) || "[]",
        ).filter((row: any) => row.request_key !== order.request_key);
        localStorage.setItem(queueKey, JSON.stringify(remaining));
        setQueue(remaining);
      }
      setMessage("All orders synced.");
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      syncing.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    if (catalog)
      localStorage.setItem("ota-react-catalog", JSON.stringify(catalog));
  }, [catalog]);
  useEffect(() => {
    sync();
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, [token, catalog, queue.length]);
  if (!saved)
    return (
      <main>
        <h1>Offline orders</h1>
        <p>Sign in online once and open Offline to load your catalogue.</p>
        <a href="/">Sign in</a>
      </main>
    );
  return (
    <section>
      <h1>Offline orders</h1>
      <p>
        Customer prices are confirmed by the server at sync. Cached data is for
        a private demo device.
      </p>
      <form
        className="card"
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const now = new Date();
          const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
          const order = {
            request_key: crypto.randomUUID(),
            user_id: saved.user_id,
            customer: data.get("customer"),
            quantities: { [String(data.get("sku"))]: data.get("quantity") },
            date: day,
          };
          try {
            const next = [
              ...JSON.parse(localStorage.getItem(queueKey) || "[]"),
              order,
            ];
            localStorage.setItem(queueKey, JSON.stringify(next));
            setQueue(next);
            setMessage("Order saved on this device.");
          } catch {
            setMessage("Device storage failed; order was not saved.");
          }
        }}
      >
        <label>
          Customer
          <select name="customer">
            {saved.customers.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Product
          <select name="sku">
            {saved.skus.map((s: any) => (
              <option key={s.id} value={s.id}>
                {s.item__name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Packets
          <input name="quantity" type="number" min="1" step="1" required />
        </label>
        <button>Save offline order</button>
      </form>
      <p role="status">{message}</p>
      <p>{queue.length} queued orders</p>
      <button disabled={!token || busy} onClick={sync}>
        Sync orders
      </button>
      {!token && (
        <p>
          <a href="/">Sign in online to sync</a>. After a browser restart, open
          /offline to capture from the cached catalogue.
        </p>
      )}
    </section>
  );
}
