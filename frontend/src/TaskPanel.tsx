import React, { useEffect, useId, useRef } from "react";
import { useTranslate } from "./language";

// A native modal keeps keyboard focus inside the task and returns it to the trigger on close.
export function TaskPanel({title, completedKey, primary = false, children}: {
  title: string; completedKey: string; primary?: boolean; children: React.ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null), heading = useId();
  const translate = useTranslate();
  useEffect(() => {dialog.current?.close();}, [completedKey]);
  return <>
    <button type="button" className={"task-trigger " + (primary ? "primary-task" : "secondary")}
      data-action-title={title} onClick={() => dialog.current?.showModal()}>{translate(title)}</button>
    <dialog ref={dialog} className="task-dialog" aria-labelledby={heading} onKeyDown={event => {
      if (event.key !== "Tab") return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]"))
        .filter(element => element.getClientRects().length > 0);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus();}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
    }}>
      <div className="dialog-heading"><h2 id={heading}>{translate(title)}</h2>
        <button type="button" className="secondary" onClick={() => dialog.current?.close()}>{translate("Close")}</button>
      </div>
      {children}
    </dialog>
  </>;
}
