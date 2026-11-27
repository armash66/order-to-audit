import React, { useState } from "react";
import { useTranslate } from "./language";

// Multiply decimal quantity and rupee rate exactly, rounding the receipt total half-up to paise.
export function receiptTotal(quantity: string, rate: string): string {
  if (!/^\d+(\.\d{1,6})?$/.test(quantity) || !/^\d+(\.\d{1,6})?$/.test(rate)) return "";
  const decimal = (value: string) => {
    const [whole, fraction = ""] = value.split(".");
    return [BigInt(whole + fraction), 10n ** BigInt(fraction.length)];
  };
  const [q, qs] = decimal(quantity), [r, rs] = decimal(rate);
  const denominator = qs * rs;
  const paise = (q * r * 200n + denominator) / (2n * denominator);
  return `${paise / 100n}.${String(paise % 100n).padStart(2, "0")}`;
}

// The rate is per selected receiving unit; total mode accommodates supplier invoice totals.
export function ReceiptPricing({quantity, unit}: {quantity: string; unit: string}) {
  const translate = useTranslate();
  const [mode, setMode] = useState("rate"), [rate, setRate] = useState("");
  const total = receiptTotal(quantity, rate);
  return <section className="receipt-pricing">
    <div className="status-tabs" role="group" aria-label={translate("Receipt pricing")}>
      <button type="button" aria-pressed={mode === "rate"} onClick={() => setMode("rate")}>{translate("Unit rate")}</button>
      <button type="button" aria-pressed={mode === "total"} onClick={() => setMode("total")}>{translate("Invoice total")}</button>
    </div>
    {mode === "rate" ? <>
      <label>{translate("Rate (₹ per selected unit)")} · {unit}
        <input aria-label={translate("Rate (₹ per selected unit)")} inputMode="decimal" required value={rate} onChange={event => setRate(event.target.value)} pattern="[0-9]+(\.[0-9]{1,6})?" />
      </label>
      <p>{translate("Quantity × rate = receipt total")}: {quantity || "—"} {unit} × ₹{rate || "—"} / {unit}</p>
      <label>{translate("Total value (₹)")}<input name="value_paise" value={total} readOnly aria-label={translate("Total value (₹)")} /></label>
    </> : <label>{translate("Total value (₹)")}<input key="manual-total" name="value_paise" inputMode="decimal" required aria-label={translate("Total value (₹)")} /></label>}
  </section>;
}
