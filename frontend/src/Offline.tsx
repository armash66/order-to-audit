import React, { useEffect, useState, useRef } from "react";
import { LanguageSwitch, useLocalize, useTranslate } from "./language";
type Props = { catalog?: any; token?: string };
const queueKey = "ota-react-orders-v1";

// Persist request keys before attempting sync; retain failed and other-user orders.
export function Offline({ catalog, token }: Props) {
  const localize = useLocalize();
  const translate = useTranslate();
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
  const [extraLines, setExtraLines] = useState<number[]>([]);
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
          throw new Error("Sync stopped. Check your connection and try again.");
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
    const reconnect = () => setMessage("Connection restored. Review queued orders, then sync.");
    window.addEventListener("online", reconnect);
    return () => window.removeEventListener("online", reconnect);
  }, []);
  if (!saved)
    return localize(
      <main>
        <LanguageSwitch />
        <h1>Offline orders</h1>
        <p>Sign in online once and open Offline to load your catalogue.</p>
        <a href="/">Sign in</a>
      </main>
    );
  return localize(
    <section>
      {!token && <LanguageSwitch />}
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
          const quantities: Record<string, string> = {};
          for (const suffix of ["", ...extraLines.map(String)]) {
            const product = String(data.get("sku" + suffix));
            const raw = String(data.get("quantity" + suffix) || "0");
            if (!/^\d+$/.test(raw)) { setMessage("Use whole packet quantities."); return; }
            const count = BigInt(raw);
            if (count > 0n) quantities[product] = String(BigInt(quantities[product] || "0") + count);
          }
          if (!Object.keys(quantities).length) { setMessage("Add at least one packet."); return; }
          const order = {
            request_key: crypto.randomUUID(),
            user_id: saved.user_id,
            customer: data.get("customer"),
            quantities,
            date: day,
          };
          try {
            const next = [
              ...JSON.parse(localStorage.getItem(queueKey) || "[]"),
              order,
            ];
            localStorage.setItem(queueKey, JSON.stringify(next));
            setQueue(next);
            setExtraLines([]);
            event.currentTarget.reset();
            setMessage("Order saved. Review it below before syncing.");
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
        {extraLines.map((line) => <React.Fragment key={line}>
          <label>Another product
            <select name={"sku" + line}>{saved.skus.map((s: any) =>
              <option key={s.id} value={s.id}>{s.item__name}</option>)}</select>
          </label>
          <label>Packets
            <input name={"quantity" + line} type="number" min="1" step="1" required />
          </label>
        </React.Fragment>)}
        <button type="button" onClick={() => setExtraLines([...extraLines, (extraLines[extraLines.length - 1] || 0) + 1])}>Add another product</button>
        <button>Save offline order</button>
      </form>
      <p role="status">{message}</p>
      <p>{queue.length} {"queued orders"}</p>
      {queue.map((order) => <div className="card" key={order.request_key}>
        <strong>{saved.customers.find((c: any) => String(c.id) === String(order.customer))?.name || order.customer}</strong>
        <p>{order.date}</p>
        <ul>{Object.entries(order.quantities).map(([id, qty]) => <li key={id}>
          {saved.skus.find((s: any) => String(s.id) === id)?.item__name || id}: {String(qty)} packets
        </li>)}</ul>
        <button type="button" onClick={() => {
          const next = queue.filter((row) => row.request_key !== order.request_key);
          localStorage.setItem(queueKey, JSON.stringify(next)); setQueue(next);
        }}>Remove queued order</button>
      </div>)}
      <button disabled={!token || busy} onClick={sync}>
        Confirm and sync orders
      </button>
      <button type="button" className="link" onClick={() => {
        if (!window.confirm(translate("Remove the cached customer list and all unsynced orders from this device?"))) return;
        localStorage.removeItem(queueKey);
        localStorage.removeItem("ota-react-catalog");
        setQueue([]);
        window.location.reload();
      }}>Clear this device</button>
      {!token && (
        <p>
          <a href="/">Sign in online to sync</a>. {"After a browser restart, open /offline to capture from the cached catalogue."}
        </p>
      )}
    </section>
  );
}
