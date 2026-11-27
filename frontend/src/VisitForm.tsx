import React, { useState } from "react";
import { ChoiceField } from "./ChoiceField";
import { TaskPanel } from "./TaskPanel";
import { useErrorText, useLocalize } from "./language";

export function VisitForm({
  customers,
  submit,
}: {
  customers: any[];
  submit: (data: any, key: string) => Promise<void>;
}) {
  const localize = useLocalize();
  const errorText = useErrorText();
  const [consent, setConsent] = useState(false),
    [position, setPosition] = useState<{
      latitude: string;
      longitude: string;
    } | null>(null),
    [message, setMessage] = useState(""),
    [messageIsError, setMessageIsError] = useState(false),
    [busy, setBusy] = useState(false),
    [key, setKey] = useState(crypto.randomUUID());
  return localize(
    <TaskPanel title="Record visit with optional GPS" completedKey={key}>
      <form className="action-fields"
        onSubmit={async (event) => {
          event.preventDefault();
          if (busy) return;
          setBusy(true);
          const values = Object.fromEntries(new FormData(event.currentTarget));
          try {
            await submit(
              { ...values, consent, ...(consent && position ? position : {}) },
              key,
            );
            setKey(crypto.randomUUID());
            setMessageIsError(false);
            setMessage("Visit recorded.");
          } catch (e) {
            setMessageIsError(true);
            setMessage((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <ChoiceField field={{name:"customer",label:"Customer"}} resetKey={key}
          options={customers.map(c => ({value:String(c.id),label:c.name}))} />
        <label>
          Route / area
          <input name="route" required />
        </label>
        <label>
          Note
          <input name="note" />
        </label>
        <label>
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => {
              setConsent(e.target.checked);
              setPosition(null);
            }}
          />{" "}
          I consent to recording this visit’s location
        </label>
        <button
          type="button"
          disabled={!consent}
          onClick={() => {
            if (!navigator.geolocation) {
              setMessageIsError(false);
              setMessage(
                "Location unavailable. A visit can be recorded without GPS.",
              );
              return;
            }
            navigator.geolocation.getCurrentPosition(
              (p) => {
                setMessageIsError(false);
                setPosition({
                  latitude: p.coords.latitude.toFixed(6),
                  longitude: p.coords.longitude.toFixed(6),
                });
                setMessage("Location captured.");
              },
              () => {
                setMessageIsError(false);
                setMessage("Location unavailable or denied. You can record without GPS.");
              },
              { timeout: 10000 },
            );
          }}
        >
          Capture location
        </button>
        <button disabled={busy}>Record visit</button>
        <p role="status">{messageIsError ? errorText(message) : message}</p>
      </form>
    </TaskPanel>
  );
}
