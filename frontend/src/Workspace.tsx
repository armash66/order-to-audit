import React, { useEffect, useState } from "react";
import { ChoiceField } from "./ChoiceField";
import { TaskPanel } from "./TaskPanel";
import { createPortal } from "react-dom";
import { Offline } from "./Offline";
import { VisitForm } from "./VisitForm";
import { LanguageSwitch, useErrorText, useLocalize, useTranslate } from "./language";

type Row = Record<string, any>;
type Request = (
  path: string,
  token: string,
  options?: RequestInit,
) => Promise<any>;
type Field = {
  name: string;
  label: string;
  options?: { value: string; label: string }[];
  value?: string;
  type?: string;
  optional?: boolean;
  money?: boolean;
  dependsOn?: string;
  optionsByValue?: Record<string, { value: string; label: string }[]>;
};
const asOptions = (rows: Row[], label: string) =>
  rows.map((row) => ({ value: row.id, label: row[label] }));
const field = (
  name: string,
  label: string,
  value = "",
  type = "text",
): Field =>
  name.endsWith("_paise")
    ? {
        name,
        label: label.replace(/ in paise.*$/, " (₹)"),
        value: value
          ? `${BigInt(value) / 100n}.${String(BigInt(value) % 100n).padStart(2, "0")}`
          : "",
        type: "text",
        money: true,
      }
    : { name, label, value, type };
const choice = (
  name: string,
  label: string,
  options: Field["options"],
): Field => ({ name, label, options });

// Display units are item-specific; conversion stays exact on the server.
const unitOptions = (base: string, finished = false) =>
  (finished ? ["packet", "carton"] : base === "g" ? ["g", "kg"] : base === "ml" ? ["ml", "L"] : ["piece"])
    .map(value => ({ value, label: value }));
// Keep measured amounts as decimal strings; omit zero order lines without Number coercion.
const measured = (data: Row, prefix: string, includeZero = false) =>
  Object.fromEntries(Object.entries(data)
    .filter(([key, value]) => key.startsWith(prefix) && (includeZero || !/^0*(\.0*)?$/.test(String(value))))
    .map(([key, quantity]) => [key.slice(prefix.length), { quantity, unit: data["unit_" + key.slice(prefix.length)] }]));

// Paise conversion uses decimal strings and BigInt only, including negative adjustments.
export function money(value: unknown): string {
  if (value === null || value === undefined) return "Unknown";
  const number = BigInt(String(value));
  const absolute = number < 0n ? -number : number;
  return `${number < 0n ? "−" : ""}₹${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}

// Display base quantities exactly: divide by 1000 with integer arithmetic, never floats.
function quantityText(value: unknown, unit: string): string {
  const quantity = BigInt(String(value));
  if (unit !== "g" && unit !== "ml") return `${quantity} ${unit}`;
  const absolute = quantity < 0n ? -quantity : quantity;
  const fraction = String(absolute % 1000n).padStart(3, "0").replace(/0+$/, "");
  return `${quantity < 0n ? "−" : ""}${absolute / 1000n}${fraction ? "." + fraction : ""} ${unit === "g" ? "kg" : "L"}`;
}

// Shared record lists keep exact values intact while sorting, filtering and paging locally.
function Table({ rows, onOpen, searchable = false, unitFor }: { rows: Row[]; onOpen?: (row: Row) => void; searchable?: boolean; unitFor?: (row: Row) => string | undefined }) {
  const localize = useLocalize(), translate = useTranslate();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState({key: "", descending: false});
  const [pageNumber, setPageNumber] = useState(0);
  const [massUnit, setMassUnit] = useState("kg"), [volumeUnit, setVolumeUnit] = useState("L");
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const statusKey = ["status", "state", "access", "category"].find(key => columns.includes(key));
  const labels: Record<string, string> = {id: "Reference", customer__name: "Customer", output_item__name: "Product",
    document_date: "Document date", expected_packets: "Expected packets", good_packets: "Good packets",
    base_unit: "Unit", value_paise: "Value (₹)", price_paise: "Price (₹)", state: "Status", status: "Status"};
  const filtered = rows.filter(row => (!searchable || !statusKey || !status || row[statusKey] === status) &&
    (!searchable || Object.values(row).some(value => [String(value), translate(String(value))]
      .some(text => text.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())))));
  const ordered = [...filtered].sort((a,b) => {
    if (!sort.key) return 0;
    const left = String(a[sort.key] ?? ""), right = String(b[sort.key] ?? "");
    const comparison = /^-?\d+$/.test(left) && /^-?\d+$/.test(right)
      ? (BigInt(left) < BigInt(right) ? -1 : BigInt(left) > BigInt(right) ? 1 : 0)
      : left.localeCompare(right, undefined, {numeric: true});
    return sort.descending ? -comparison : comparison;
  });
  const pages = Math.max(1, Math.ceil(ordered.length / 20)), current = Math.min(pageNumber, pages - 1);
  return localize(<section className="record-list">
    {searchable && <>
      {statusKey && <div className="status-tabs" role="group" aria-label="Filter status">
        {["", ...new Set(rows.map(row => String(row[statusKey])))].map(value =>
          <button key={value} aria-pressed={status === value} onClick={() => {setStatus(value); setPageNumber(0);}}>
            {value ? translate(value) : translate("All statuses")} <span>{value ? rows.filter(row => String(row[statusKey]) === value).length : rows.length}</span>
          </button>)}
      </div>}
      <div className="table-toolbar">
        <label>Search records<input type="search" value={query} onChange={event => {setQuery(event.target.value); setPageNumber(0);}} /></label>
        <button className="secondary" type="button" onClick={() => {setQuery(""); setStatus(""); setPageNumber(0);}}>Clear filters</button>
        <span className="record-count">{filtered.length} {translate("Records")}</span>
      </div>
    </>}
    {!rows.length ? <p className="empty-state">No records yet.</p> : !filtered.length ? <p className="empty-state">No matching records.</p> :
      <div className="table-wrap"><table><thead><tr>{columns.map(key =>
        <th key={key} scope="col" className={key.endsWith("paise") || /quantity|packets/.test(key) ? "numeric" : undefined} aria-sort={sort.key === key ? sort.descending ? "descending" : "ascending" : "none"}>
          <button className="sort-button" onClick={() => setSort({key, descending: sort.key === key && !sort.descending})}>
            {translate(labels[key] || key.replaceAll("_", " "))}<span aria-hidden="true">{sort.key === key ? sort.descending ? " ↓" : " ↑" : " ↕"}</span>
          </button>
          {key === "quantity" && unitFor && <div className="column-units">
            {rows.some(row => unitFor(row) === "g") && <div role="group" aria-label="g / kg">
              {["g", "kg"].map(unit => <button key={unit} aria-pressed={massUnit === unit} onClick={() => setMassUnit(unit)}>{unit}</button>)}
            </div>}
            {rows.some(row => unitFor(row) === "ml") && <div role="group" aria-label="ml / L">
              {["ml", "L"].map(unit => <button key={unit} aria-pressed={volumeUnit === unit} onClick={() => setVolumeUnit(unit)}>{unit}</button>)}
            </div>}
          </div>}</th>)}{onOpen && <th scope="col">Action</th>}</tr></thead>
        <tbody>{ordered.slice(current * 20, current * 20 + 20).map((row,index) => <tr key={row.id || row.code || index}>
          {columns.map(key => <td key={key} className={key.endsWith("paise") || /quantity|packets/.test(key) ? "numeric" : undefined}>
            {key === "quantity" && unitFor?.(row) ? <>
              <span className="stock-quantity">{(unitFor(row) === "g" && massUnit === "g") || (unitFor(row) === "ml" && volumeUnit === "ml")
                ? `${row[key]} ${unitFor(row)}` : quantityText(row[key], unitFor(row)!)}</span>
            </> : ["status","state","access"].includes(key) ? <span className={"status-badge status-" + String(row[key]).toLowerCase()}>{translate(String(row[key]))}</span> : display(row[key],key)}
          </td>)}{onOpen && <td className="row-action"><button className="link" onClick={() => onOpen(row)}>Open</button></td>}
        </tr>)}</tbody></table></div>}
    {pages > 1 && <div className="pagination"><button className="secondary" disabled={current === 0} onClick={() => setPageNumber(current - 1)}>Previous</button>
      <span>{current + 1} / {pages}</span><button className="secondary" disabled={current + 1 === pages} onClick={() => setPageNumber(current + 1)}>Next</button></div>}
  </section>);
}

// Show ratios as percentages, rounded half-up to two decimals using integers only.
function percentage(ratio: Row | null): string {
  if (!ratio) return "—";
  const numerator = BigInt(ratio.numerator), denominator = BigInt(ratio.denominator);
  const absolute = numerator < 0n ? -numerator : numerator;
  const scaled = (absolute * 20000n + denominator) / (2n * denominator);
  return `${numerator < 0n ? "−" : numerator > 0n ? "+" : ""}${scaled / 100n}${scaled % 100n ? "." + String(scaled % 100n).padStart(2, "0").replace(/0$/, "") : ""}%`;
}

// Separate output, consumption and costing so each figure has a business meaning.
function ProductionSummary({report, standards}: {report: Row; standards: Row[]}) {
  const translate = useTranslate(), localize = useLocalize();
  const status = (ratio: Row | null, flagged: boolean) => !ratio ? translate("Not recorded") : translate(flagged ? "Flagged" : "Within tolerance");
  const metric = (label: string, value: React.ReactNode) => <div><dt>{translate(label)}</dt><dd>{value ?? "—"}</dd></div>;
  return localize(<section className="production-summary" aria-label="Variance and costing">
    <section className="card">
      <h2>Production output</h2>
      <dl className="detail-metrics">
        {metric("Expected packets", report.expected_packets)}{metric("Good packets", report.good_packets)}
        {metric("Yield variance", <><strong>{percentage(report.yield.ratio)}</strong><span className={"variance-state " + (report.yield.flagged ? "flagged" : "")}>{status(report.yield.ratio, report.yield.flagged)}</span></>)}
        {metric("Unclassified shortfall", report.unclassified_shortfall)}
      </dl>
    </section>
    <section className="card consumption-card">
      <div className="section-heading"><h2>Material consumption</h2><span>{translate("Tolerance")}: {percentage({numerator: report.tolerance_bps, denominator: "10000"}).replace("+", "")}</span></div>
      <p>Flags use the current tolerance. Packaging damage is included in issued quantities.</p>
      <div className="table-wrap"><table><thead><tr><th>Item</th><th>Planned</th><th>Issued</th><th>Variance</th><th>Status</th></tr></thead>
        <tbody>{Object.entries(report.consumption).map(([code, entry]) => {
          const row = entry as Row, item = standards.find(s => s.item__code === code);
          const quantity = (value: unknown) => value == null ? "—" : quantityText(value, item?.item__base_unit || "piece");
          return <tr key={code}><td>{translate(item?.item__name || code)}</td><td className="numeric">{quantity(row.planned)}</td><td className="numeric">{quantity(row.actual)}</td><td className="numeric">{percentage(row.ratio)}</td><td><span className={"variance-state " + (row.flagged ? "flagged" : "")}>{status(row.ratio, row.flagged)}</span></td></tr>;
        })}</tbody></table></div>
    </section>
    <div className="detail-columns">
      <section className="card"><h2>Run costing</h2><dl className="cost-breakdown">
        {metric("Materials and packaging", money(report.materials_paise))}{metric("Overheads", money(report.overhead_paise))}
        {metric("Total run cost", money(report.total_paise))}{metric("Cost per good packet", report.display_cost_paise == null ? "—" : money(report.display_cost_paise))}
        {metric("Margin per packet", display(report.margin_paise, "margin"))}
      </dl><p>Total run cost divided by good packets. Amounts are rounded only for display.</p>
      <p>Finished-goods stock value includes materials only; overheads are included in run costing.</p></section>
      <section className="card"><h2>Packaging damage</h2>
        <dl className="cost-breakdown">{Object.entries(report.damaged_packaging).map(([code, value]) => <React.Fragment key={code}>{metric(standards.find(s => s.item__code === code)?.item__name || code, quantityText(value, "piece"))}</React.Fragment>)}</dl>
        {!Object.keys(report.damaged_packaging).length && <p>Not recorded</p>}
        <p>Packaging damage and unclassified output shortfall are separate measures.</p>
      </section>
    </div>
  </section>);
}

function display(value: any, key = ""): React.ReactNode {
  if (key.endsWith("paise") && value == null) return "Unknown";
  if (value === null || value === undefined) return "—";
  if (key.endsWith("paise") && typeof value === "string") return money(value);
  // Cost ratios stay exact until half-up rounding for the currency display.
  if (["unit_cost", "margin"].includes(key) && typeof value === "object" && "numerator" in value) {
    const numerator = BigInt(value.numerator), denominator = BigInt(value.denominator);
    const absolute = numerator < 0n ? -numerator : numerator;
    const rounded = (2n * absolute + denominator) / (2n * denominator);
    return money(numerator < 0n ? -rounded : rounded);
  }
  if (typeof value === "object" && "numerator" in value)
    return <>{value.numerator}/{value.denominator} {"(exact)"}</>;
  if (Array.isArray(value))
    return value.length ? (
      <Table
        rows={value.map((v) => (typeof v === "object" ? v : { value: v }))}
      />
    ) : (
      "None"
    );
  if (typeof value === "object")
    return (
      <dl className="document-facts">
        {Object.entries(value).map(([k, v]) => (
          <React.Fragment key={k}>
            <dt>{k.replaceAll("_", " ")}</dt>
            <dd>{display(v, k)}</dd>
          </React.Fragment>
        ))}
      </dl>
    );
  return String(value);
}


function ActionForm({
  title,
  fields,
  submit,
  customerPrices,
  primary = false,
}: {
  title: string;
  fields: Field[];
  submit: (data: Row, key: string) => Promise<void>;
  customerPrices?: (id: string) => Promise<Row[]>;
  primary?: boolean;
}) {
  const translate = useTranslate();
  const localize = useLocalize();
  const errorText = useErrorText();
  const [prices,setPrices]=useState<Row[]>([]);
  const [selections, setSelections] = useState<Record<string, string>>({});
  async function refreshPrices(id:string){if(customerPrices)try{setPrices(await customerPrices(id));}catch{setPrices([]);}}
  useEffect(()=>{const id=fields.find(f=>f.name==='customer')?.options?.[0]?.value;if(id)refreshPrices(id);},[]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [key, setKey] = useState(crypto.randomUUID());
  return localize(
    <TaskPanel title={title} completedKey={key} primary={primary}>
      <form className="action-fields"
        onChange={event=>{const target=event.target as HTMLInputElement;setSelections(old=>({...old,[target.name]:target.value}));if(target.name==='customer')refreshPrices(target.value);}}
        onSubmit={async (event) => {
          event.preventDefault();
          if (busy) return;
          setBusy(true);
          setError("");
          const form = event.currentTarget;
          const data = Object.fromEntries(new FormData(form));
          try {
            for (const f of fields.filter((f) => f.money)) {
              const value = String(data[f.name] || "").trim();
              if (!value && f.optional) continue;
              if (!/^\d+(\.\d{1,2})?$/.test(value))
                throw new Error("Enter money with at most two decimal places.");
              const [whole, fraction = ""] = value.split(".");
              data[f.name] = String(
                BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0")),
              );
            }
            await submit(data, key);
            setKey(crypto.randomUUID());
            form.reset();
            setSelections({});
            const customerId=fields.find(f=>f.name==='customer')?.options?.[0]?.value;if(customerId)refreshPrices(customerId);
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {fields.map((f) => f.options ? <ChoiceField key={f.name + (f.dependsOn ? selections[f.dependsOn] || "" : "")}
          field={f} resetKey={key}
          options={f.optionsByValue?.[selections[f.dependsOn!] || fields.find(field => field.name === f.dependsOn)?.options?.[0]?.value || ""] || f.options} /> : (
          <label key={f.name}>
            {translate(f.label)}
              <input
                aria-label={translate(f.label)}
                name={f.name}
                defaultValue={f.value}
                type={f.type === "decimal" ? "text" : f.type || "text"}
                inputMode={f.type === "decimal" ? "decimal" : undefined}
                required={!f.optional}
              />
          </label>
        ))}
        {error && <p role="alert">{errorText(error)}</p>}
        {prices.length>0&&<div className="notice">Prices before GST:{prices.map(price=><p key={price.sku_id}>{price.name}: {money(price.price_paise)} · {price.label}</p>)}</div>}
        <button disabled={busy}>{busy ? "Saving…" : translate(title)}</button>
      </form>
    </TaskPanel>
  );
}

export function Workspace({
  token,
  user,
  request,
}: {
  token: string;
  user: Row;
  request: Request;
}) {
  const translate = useTranslate(), localize = useLocalize(), errorText = useErrorText();
  const [catalog, setCatalog] = useState<Row | null>(null),
    [page, setPage] = useState("orders"),
    [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [selected, setSelected] = useState<string | null>(null),
    [sourceDetail, setSourceDetail] = useState<Row | null>(null),
    [recallDetail, setRecallDetail] = useState<Row | null>(null),
    [setupTab, setSetupTab] = useState("staff"),
    [accountName, setAccountName] = useState<string | null>(null),
    [revision, setRevision] = useState(0);
  const [kind, setKind] = useState("sales"),
    [start, setStart] = useState("2026-11-01"),
    [end, setEnd] = useState("2026-11-30");
  const admin = user.is_staff || user.roles.includes("admin");
  const production = admin || user.roles.includes("production");
  const sales = admin || user.roles.includes("salesman");
  const reports =
    admin ||
    user.roles.some((r: string) => ["accountant", "owner"].includes(r));
  const stock = production || reports;
  const load = (path: string, options?: RequestInit) =>
    request("/workspace" + path, token, options);
  useEffect(() => {
    load("/catalog")
      .then((c) => {
        setCatalog(c);
        setStart(c.today.slice(0, 7) + "-01");
        setEnd(c.today);
      })
      .catch((e) => setError(e.message));
    setPage(production && !sales && !reports ? "production" : "orders");
  }, []);
  useEffect(() => {
    if (!catalog) return;
    let active = true;
    setError("");
    setData(null);
    setSourceDetail(null);
    setRecallDetail(null);
    let route =
      page === "setup" ? "/accounts" : page === "reports"
        ? `/reports/${kind}?start=${start}&end=${end}`
        : `/${page}${selected ? "/" + selected : ""}`;
    if (page === "stock") {
      request(selected ? `/stock/${selected}/ledger` : "/stock", token)
        .then((d) => active && setData(d))
        .catch((e) => active && setError(e.message));
    } else if (page === "prices" || page === "offline") setData({});
    else
      load(route)
        .then((d) => active && setData(d))
        .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [page, selected, revision, catalog, kind, start, end]);
  async function command(action: string, values: Row, key: string) {
    await load("/commands", {
      method: "POST",
      body: JSON.stringify({ action, request_key: key, data: values }),
    });
    const messages: Record<string, string> = {
      "order.create": "Order submitted.", "order.approve": "Order approved and stock reserved.",
      "order.invoice": "Invoice posted. Stock moves at dispatch.", "order.dispatch": "Dispatch recorded and stock updated.",
      "order.payment": "Payment recorded and outstanding updated.", "order.reject": "Order rejected and reservation released.",
      "production.create": "Production run created.", "production.issue": "Materials issued and stock updated.",
      "production.complete": "Production completed and finished stock received.", "receipt": "Receipt posted and stock updated.",
      "account.create": "Staff account created. The first sign-in requires a new password.",
    };
    setNotice(messages[action] || "Saved successfully.");
    if (action.startsWith("master.")) setCatalog(await load("/catalog"));
    setRevision((r) => r + 1);
  }
  async function download(path: string, name: string) {
    try {
      const response = await fetch("/api/workspace" + path, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await response.text());
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function shareInvoice(id: string) {
    try {
      const response = await fetch(`/api/workspace/invoices/${id}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Could not load invoice.");
      const file = new File([await response.blob()], "invoice.pdf", {
        type: "application/pdf",
      });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: translate("Invoice") });
      } else {
        await download(`/invoices/${id}/pdf`, "invoice.pdf");
        setError(
          "PDF downloaded. Attach it to your email or WhatsApp message.",
        );
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    }
  }
  function navigate(next: string) {
    if (next === page && selected === null) return;
    setData(null);
    setSourceDetail(null);
    setRecallDetail(null);
    setNotice("");
    setPage(next);
    setSelected(null);
  }
  if (!catalog) return <p>{error ? errorText(error) : translate("Loading workspace…")}</p>;
  const dateField = field("date", "Document date", catalog.today, "date");
  const customer = choice(
    "customer",
    "Customer",
    asOptions(catalog.customers, "name"),
  );
  const sku = choice("sku", "Product", asOptions(catalog.skus, "item__name"));
  const item = choice("item", "Item", asOptions(catalog.items, "name"));
  const stockUnit = (row: Row) => {
    const item = catalog.items.find((item: Row) => item.code === row.code);
    return item?.category === "finished" ? translate("packets") : item?.base_unit === "piece" ? translate("piece") : item?.base_unit;
  };
  const shortage = page === "orders" && data?.status === "submitted" && data.stock?.some((row: Row) => BigInt(row.shortage) > 0n);
  const nextTitle = selected && data && !Array.isArray(data)
    ? page === "orders" && admin
      ? shortage ? "" : data.status === "submitted" ? "Approve and reserve" : data.status === "approved" ? "Post invoice"
        : data.status === "invoiced" ? "Dispatch remaining order" : data.status === "dispatched" && data.invoice?.status === "posted" && BigInt(data.invoice.outstanding) > 0n ? "Record payment" : ""
      : page === "production" && production ? data.state === "draft" ? "Issue raw materials" : data.state === "issued" ? "Complete production" : "" : ""
    : "";
  // Reveal a task without posting anything; the operator still reviews and submits its form.
  function openTask(title: string) {
    const trigger = Array.from(document.querySelectorAll<HTMLButtonElement>("button[data-action-title]"))
      .find(button => button.dataset.actionTitle === title);
    trigger?.click();
  }
  const form = (
    title: string,
    action: string,
    fields: Field[],
    fixed: Row = {},
    transform?: (d: Row) => Row,
  ) => (
    <ActionForm
      key={title + selected}
      title={title}
      primary={title === nextTitle}
      fields={fields}
      customerPrices={action==='order.create'?id=>load('/prices/'+id):undefined}
      submit={(d, key) =>
        command(action, { ...fixed, ...(transform ? transform(d) : d) }, key)
      }
    />
  );
  const collect = (d: Row, prefix: string, includeZero = false) =>
    Object.fromEntries(
      Object.entries(d)
        .filter(
          ([k, v]) => k.startsWith(prefix) && (includeZero || String(v) !== "0") && v !== "",
        )
        .map(([k, v]) => [k.slice(prefix.length), v]),
    );
  const menu = [
    ...(reports ? ["dashboard"] : []),
    ...(sales || reports ? ["orders"] : []),
    ...(production ? ["production"] : []),
    ...(stock ? ["stock", "batches"] : []),
    ...(stock ? ["audit"] : []),
    ...(sales || reports ? ["reports", "visits"] : []),
    ...(sales ? ["offline"] : []),
    ...(admin ? ["prices"] : []),
    ...(admin ? ["setup"] : []),
  ];
  const dailyMenu = menu.filter((name) => ["dashboard", "orders", "production", "stock", "reports"].includes(name));
  const toolsMenu = menu.filter((name) => !dailyMenu.includes(name));
  return localize(
    <>
      {createPortal(localize(<nav className="sidebar-nav" aria-label="Workspace">
        {[{heading:'Daily work',names:dailyMenu},{heading:'Tools & setup',names:toolsMenu}].map((group) =>
          <div className="nav-group" key={group.heading}>
            <span>{translate(group.heading)}</span>
            {group.names.map((name) => <button key={name}
              aria-current={page === name ? "page" : undefined}
              onClick={() => navigate(name)}>
              {translate(name[0].toUpperCase() + name.slice(1))}</button>)}
          </div>)}
      </nav>), document.getElementById("workspace-navigation")!)}
      <div className="page-heading"><h1>
        {translate(page[0].toUpperCase() + page.slice(1))}
        {selected && " #" + selected}
      </h1><span className="page-date">{catalog.today}</span></div>
      {selected && (
        <button onClick={() => setSelected(null)}>← Back to list</button>
      )}
      {error && <p role="alert">{errorText(error)}</p>}
      {notice && <p role="status" className="notice">{notice}</p>}
      {data && ["orders", "production"].includes(page) && <section className="task-guide" aria-label="Next step">
        <div><strong>Next step</strong>
          {!selected && page === "orders" && <p>Open an order to review stock and continue billing, or start a new order.</p>}
          {!selected && page === "production" && <p>Receive purchased materials, then create a run. Open a run to issue materials and record output.</p>}
          {selected && shortage && <p>Stock is short. Review the shortage below and replenish before approving.</p>}
          {selected && !shortage && nextTitle && <p>{translate(nextTitle)}</p>}
          {selected && !shortage && !nextTitle && <p>Review this record below. Available actions depend on its status and your role.</p>}
        </div>
        <div className="task-buttons">
          {!selected && page === "orders" && sales && <button onClick={() => openTask("Submit order")}>New order</button>}
          {!selected && page === "production" && production && <>
            <button onClick={() => openTask("Receive materials")}>Receive materials</button>
            <button className="secondary" onClick={() => openTask("Create production run")}>Create production run</button>
          </>}
          {nextTitle && <button onClick={() => openTask(nextTitle)}>Continue</button>}
        </div>
      </section>}
      {admin && page === "orders" && !selected && <section className="setup-shortcuts" aria-label="Factory setup checklist">
        <h2>Factory setup checklist</h2>
        <p>Review the demo records and prepare your staff before daily work.</p>
        {[['staff','Staff'], ['parties','Customers & suppliers'], ['items','Materials & products'], ['recipes','Recipes']].map(([tab,label]) =>
          <p key={tab}><button type="button" onClick={() => {setSetupTab(tab); navigate("setup");}}>{translate(label)}</button>
          {tab === 'parties' && ` · ${catalog.customers.length} / ${catalog.suppliers.length}`}
          {tab === 'items' && ` · ${catalog.items.length} / ${catalog.skus.length}`}
          {tab === 'recipes' && ` · ${catalog.boms.length}`}</p>)}
        <p>Counts include seeded records; review them before recording transactions.</p>
      </section>}
      {page === "orders" && !selected && (
        <>
          {Array.isArray(data) && (
            <Table searchable rows={data} onOpen={(row) => setSelected(row.id)} />
          )}
          {sales &&
            form(
              "Submit order",
              "order.create",
              [
                customer,
                dateField,
                ...catalog.skus.flatMap((s: Row) => [
                  field(
                    "qty_" + s.id,
                    translate(s["item__name"]) + " · " + translate("Quantity (0 to omit)"),
                    "0",
                    "number",
                  ),
                  choice("unit_" + s.id, translate(s["item__name"]) + " · " + translate("Unit"), unitOptions("piece", true)),
                ]),
              ],
              {},
              (d) => ({
                customer: d.customer,
                date: d.date,
                quantities: measured(d, "qty_"),
              }),
            )}

        </>
      )}
      {page === "orders" && selected && data && !Array.isArray(data) && (
        <>
          <h2>
            {data.customer} · {translate(data.status)}
          </h2>
          <ol className="workflow-steps" aria-label="Order status">
            {["submitted", "approved", "invoiced", "dispatched"].map((stage,index) => <li key={stage}
              aria-current={data.status === stage ? "step" : undefined}
              className={index <= ["submitted", "approved", "invoiced", "dispatched"].indexOf(data.status) ? "reached" : ""}>
              <span aria-hidden="true">{index + 1}</span>{translate(stage)}</li>)}
          </ol>
          <Table rows={data.lines} />
          <h3>Stock check</h3>
          <Table rows={data.stock} />
          {admin && (
            <>
              {data.status === "submitted" &&
                form("Approve and reserve", "order.approve", [], {
                  id: selected,
                })}
              {["submitted", "approved"].includes(data.status) &&
                form(
                  "Reject order",
                  "order.reject",
                  [field("reason", "Reason")],
                  { id: selected },
                )}
              {data.status === "approved" &&
                form("Post invoice", "order.invoice", [dateField], {
                  id: selected,
                })}
              {data.status === "invoiced" &&
                form(
                  "Dispatch remaining order",
                  "order.dispatch",
                  [dateField],
                  { id: selected },
                )}
              {!data.invoice &&
                form(
                  "Edit order",
                  "order.edit",
                  data.lines.flatMap((line: Row) => [
                    field(
                      "qty_" + line.id,
                      translate(line["sku__item__name"]) + " " + translate("packets"),
                      line.quantity,
                      "number",
                    ),
                    field(
                      "price_" + line.id + "_paise",
                      "Price in paise",
                      line.price_paise,
                      "number",
                    ),
                  ]),
                  { id: selected },
                  (d) => ({
                    lines: Object.fromEntries(
                      data.lines.map((line: Row) => [
                        line.id,
                        [d["qty_" + line.id], d["price_" + line.id + "_paise"]],
                      ]),
                    ),
                  }),
                )}
            </>
          )}
          {data.invoice && (
            <section className="card">
              <h2>Invoice {data.invoice.number}</h2>
              <dl className="detail-metrics invoice-totals">
                <div><dt>Taxable</dt><dd>{money(data.invoice.taxable_paise)}</dd></div>
                <div><dt>CGST</dt><dd>{money(data.invoice.cgst_paise)}</dd></div>
                <div><dt>SGST</dt><dd>{money(data.invoice.sgst_paise)}</dd></div>
                <div><dt>IGST</dt><dd>{money(data.invoice.igst_paise)}</dd></div>
                <div><dt>Total</dt><dd>{money(data.invoice.total_paise)}</dd></div>
                <div><dt>Outstanding</dt><dd>{money(data.invoice.outstanding)}</dd></div>
              </dl>
              <button
                onClick={() =>
                  download(`/invoices/${data.invoice.id}/pdf`, "invoice.pdf")
                }
              >
                Download invoice PDF
              </button>
              <button onClick={() => shareInvoice(data.invoice.id)}>
                Share invoice PDF
              </button>
              <p>Download the PDF, then attach it to your message. These links open a draft; nothing is sent automatically.</p>
              <a target="_blank" rel="noopener noreferrer" href={"https://wa.me/?text=" + encodeURIComponent(
                `${translate("Invoice")} ${data.invoice.number} · ${translate("Total")} ${money(data.invoice.total_paise)}`
              )}>Share via WhatsApp</a>{" · "}
              <a href={"mailto:?subject=" + encodeURIComponent(`${translate("Invoice")} ${data.invoice.number}`)
                + "&body=" + encodeURIComponent(`${translate("Total")} ${money(data.invoice.total_paise)}`)}>Share via email</a>
              {admin && data.invoice.status === "posted" && (
                <>
                  {data.invoice.outstanding !== "0" && form(
                    "Record collection follow-up", "collection.followup",
                    [field("note", "Contact note"), field("next_contact", "Next contact date", catalog.today, "date")],
                    { invoice: data.invoice.id },
                  )}
                  {form(
                    "Record payment",
                    "order.payment",
                    [
                      field(
                        "amount_paise",
                        "Amount in paise (₹4,000 = 400000)",
                        "",
                        "number",
                      ),
                      dateField,
                    ],
                    { id: selected },
                  )}
                  {form(
                    "Partial dispatch",
                    "order.dispatch",
                    [
                      dateField,
                      ...data.invoice.fulfilment.map((r: Row) =>
                        field(
                          "qty_" + r.item_id,
                          translate(r.name) + " · " + translate("remaining") + " " + r.remaining,
                          "0",
                          "number",
                        ),
                      ),
                    ],
                    { id: selected },
                    (d) => ({ date: d.date, quantities: collect(d, "qty_") }),
                  )}
                  {form(
                    "Accept sealed-goods return",
                    "order.return",
                    [
                      dateField,
                      field("reason", "Reason"),
                      ...data.invoice.fulfilment.map((r: Row) =>
                        field(
                          "qty_" + r.item_id,
                          translate(r.name) + " · " + translate("returnable") + " " + r.returnable,
                          "0",
                          "number",
                        ),
                      ),
                    ],
                    { id: selected },
                    (d) => ({
                      date: d.date,
                      reason: d.reason,
                      quantities: collect(d, "qty_"),
                    }),
                  )}
                  {form(
                    "Full unpaid undispatched credit",
                    "order.credit",
                    [dateField, field("reason", "Reason")],
                    { id: selected },
                  )}
                  <ActionForm
                    title="Generate local mock document"
                    fields={[
                      choice("kind", "Mock format", [
                        { value: "e_invoice", label: "e-Invoice" },
                        { value: "e_waybill", label: "e-Way Bill" },
                      ]),
                    ]}
                    submit={async (d, key) => {
                      const result = await load("/commands", {
                        method: "POST",
                        body: JSON.stringify({
                          action: "mock",
                          request_key: key,
                          data: { ...d, invoice: data.invoice.id },
                        }),
                      });
                      const url = URL.createObjectURL(
                        new Blob([JSON.stringify(result)], {
                          type: "application/json",
                        }),
                      );
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "MOCK-document.json";
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  />
                </>
              )}
              {data.invoice.followups?.length > 0 && <>
                <h3>Collection follow-ups</h3><Table rows={data.invoice.followups} />
              </>}
            </section>
          )}
          {data.suggestions && (
            <section className="card" aria-label="Shortage resolution">
              <h2>Shortage resolution</h2>
              {data.suggestions.map((plan: Row, index: number) => <div key={index}>
                <p>{plan.uncovered} {translate("uncovered packets")} · {plan.required_batches} {translate("batches needed")} · {plan.feasible_batches} {translate("feasible now.")}</p>
                <strong>{translate(plan.next_action)}</strong>
                {plan.required_batches !== "0" && <Table rows={plan.inputs} />}
              </div>)}
              {data.suggestions.some((plan: Row) => plan.required_batches !== "0") &&
                <button onClick={() => navigate("production")}>Open production and receipts</button>}
            </section>
          )}
        </>
      )}
      {page === "production" && !selected && (
        <>
          {Array.isArray(data) && (
            <Table searchable rows={data} onOpen={(row) => setSelected(row.id)} />
          )}
          {form("Create production run", "production.create", [
            choice(
              "bom",
              "Product / BOM",
              catalog.boms.map((b: Row) => ({
                value: b.id,
                label: translate(b["sku__item__name"]) + " · v" + b.version,
              })),
            ),
            field("batches", "Batches", "1", "number"),
            dateField,
            { ...field("expiry", "Output expiry", "", "date"), optional: true },
          ])}
          {form(
            "Receive materials",
            "receipt",
            [
              choice(
                "supplier",
                "Supplier",
                asOptions(catalog.suppliers, "name"),
              ),
              item,
              field(
                "quantity",
                "Quantity",
                "",
                "decimal",
              ),
              { ...choice("unit", "Unit", unitOptions("g")), dependsOn: "item",
                optionsByValue: Object.fromEntries(catalog.items.map((i: Row) => [i.id, unitOptions(i.base_unit, i.category === "finished")])) },
              field("value_paise", "Total value in paise", "", "number"),
              dateField,
              { ...field("batch", "Supplier batch code"), optional: true },
              { ...field("expiry", "Expiry date", "", "date"), optional: true },
            ],
            {},
            (d) => ({
              supplier: d.supplier,
              date: d.date,
              lines: [
                {
                  item: d.item,
                  quantity: d.quantity,
                  unit: d.unit,
                  value_paise: d.value_paise,
                },
              ],
              lots:
                d.batch || d.expiry
                  ? {
                      [catalog.items.find((i: Row) => i.id === d.item).code]: {
                        code: d.batch || null,
                        expiry: d.expiry || null,
                      },
                    }
                  : undefined,
            }),
          )}

        </>
      )}
      {page === "production" && selected && data && !Array.isArray(data) && (
        <>
          <h2>
            {data.name} · {translate(data.state)}
          </h2>
          <ProductionSummary report={data.report} standards={data.standards} />
          {data.state === "draft" &&
            form(
              "Issue raw materials",
              "production.issue",
              data.standards
                .filter((s: Row) => s.stage === "raw")
                .flatMap((s: Row) => [
                  field(
                    "qty_" + s.item__code,
                    translate(s.item__name) + " · " + translate("Quantity"),
                    s.quantity,
                    "decimal",
                  ),
                  choice("unit_" + s.item__code, translate(s.item__name) + " · " + translate("Unit"), unitOptions(s.item__base_unit)),
                ]),
              { id: selected },
              (d) => ({ actual: measured(d, "qty_", true) }),
            )}
          {data.state === "issued" &&
            form(
              "Complete production",
              "production.complete",
              [
                field("good_packets", "Good packets", "", "number"),
                ...data.standards
                  .filter((s: Row) => s.stage === "packaging")
                  .flatMap((s: Row) => [
                    field(
                      "qty_" + s.item__code,
                      translate(s.item__name) + " " + translate("total issued (including damage)"),
                      s.quantity,
                      "number",
                    ),
                    field(
                      "damage_" + s.item__code,
                      translate(s.item__name) + " " + translate("damaged"),
                      "0",
                      "number",
                    ),
                  ]),
              ],
              { id: selected },
              (d) => ({
                actual: collect(d, "qty_", true),
                damaged: collect(d, "damage_"),
                good_packets: d.good_packets,
              }),
            )}
          {form(
            "Add overhead",
            "production.overhead",
            [
              field("label", "Description"),
              field("amount_paise", "Amount in paise", "", "number"),
              dateField,
            ],
            { id: selected },
          )}
          {data.state === "completed" && form(
            "Explain production loss", "run.loss_note",
            [field("reason", "Loss reason"), field("note", "Explanation")],
            { run: selected },
          )}
          {data.loss_notes?.length > 0 && <section className="card">
            <h2>Production loss explanations</h2><Table rows={data.loss_notes} />
          </section>}
          {data.state === "draft" &&
            form(
              "Edit batch count",
              "production.edit",
              [field("batches", "Batches", "1", "number")],
              { id: selected },
            )}
          {admin &&
            form("Set variance tolerance", "tolerance", [
              field(
                "basis_points",
                "Tolerance basis points (3% = 300)",
                "300",
                "number",
              ),
            ])}
          {admin &&
            form(
              "Reverse run",
              "production.reverse",
              [dateField, field("reason", "Reason")],
              { id: selected },
            )}
        </>
      )}
      {page === "stock" && Array.isArray(data) && (
        <Table searchable unitFor={stockUnit} rows={data.map(({id, base_unit, ...row}: Row) => row)} onOpen={(row) => setSelected(row.code)} />
      )}
      {page === "stock" && selected && data && !Array.isArray(data) && (
        <>
          <h2>{data.item.name}</h2>
          <Table rows={data.movements} unitFor={() => stockUnit({code: selected})} onOpen={async (row) => {
            try {
              setSourceDetail(await load("/sources/" + row.posting_id));
              setError("");
            } catch (e) { setError((e as Error).message); }
          }} />
          {sourceDetail && <section className="card" aria-label="Source document">
            <h2>{translate("Source document")} · {translate("posting")} #{sourceDetail.id}</h2>
            <p>Document</p>{display(sourceDetail.document)}
            <h3>Source lines</h3><Table rows={sourceDetail.lines || []} />
            <button onClick={() => setSourceDetail(null)}>Close source</button>
          </section>}
        </>
      )}
      {page === "stock" &&
        admin &&
        !selected &&
        form("Record adjustment", "adjustment", [
          item,
          field("quantity", "Signed quantity in base units", "", "number"),
          {
            ...field(
              "value_paise",
              "Positive adjustment value in paise",
              "",
              "number",
            ),
            optional: true,
          },
          field("reason", "Reason"),
          dateField,
        ])}
      {page === "batches" && data && (
        <>
          <h2>Lots and quality status</h2>
          <Table rows={data.lots} onOpen={async (row) => {
            try { setRecallDetail(await load("/recall/" + row.id)); setError(""); }
            catch (e) { setError((e as Error).message); }
          }} />
          {recallDetail && <section className="card" aria-label="Batch recall trace">
            <h2>{translate("Trace lot")} {recallDetail.lot.code}</h2>
            <p>Original movements and source documents</p>
            <Table rows={recallDetail.movements} onOpen={async (row) => {
              try { setSourceDetail(await load("/sources/" + row.posting_id)); setError(""); }
              catch (e) { setError((e as Error).message); }
            }} />
            {sourceDetail && <div className="notice">
              <h3>{translate("Source posting")} #{sourceDetail.id}</h3>
              {display(sourceDetail.document)}<Table rows={sourceDetail.lines || []} />
            </div>}
            <h3>Production runs</h3>{display(recallDetail.production_run_ids)}
            <h3>Finished lots</h3><Table rows={recallDetail.finished_lots} />
            <h3>Affected dispatches and customers</h3><Table rows={recallDetail.dispatches} />
          </section>}
          <h2>Reorder alerts</h2><Table rows={data.alerts} />
          {production && form("Hold or release finished lot", "quality", [
            choice("lot", "Finished lot", data.lots.filter((r: Row) => r.category === "finished" && BigInt(r.quantity) > 0n)
              .map((r: Row) => ({value:r.id,label:translate(r.item) + " / " + r.code + " (" + r.quantity + ")"}))),
            choice("status", "Quality decision", [
              {value:"held",label:"Hold from dispatch"},{value:"released",label:"Release"}]),
            field("reason", "Reason"),
          ])}
          {admin &&
            form("Set reorder minimum", "reorder", [
              item,
              field("minimum", "Minimum in base units", "0", "number"),
            ])}
        </>
      )}
      {page === "audit" && Array.isArray(data) && (
        <section className="card" aria-label="Audit history">
          <h2>Recent audit history</h2>
          <p>Latest 100 recorded actions. Each entry shows the actor, time, document and values captured before and after the action.</p>
          <Table rows={data} />
        </section>
      )}
      {page === "setup" && admin && Array.isArray(data) && <>
        <p>Set up staff, trading partners and products before taking orders or recording production.</p>
        <nav className="tabs setup-tabs" aria-label="Setup areas">
          {[['staff','Staff'],['parties','Customers & suppliers'],['items','Materials & products'],['recipes','Recipes']].map(([value,label]) =>
            <button key={value} aria-current={setupTab===value?'page':undefined}
              onClick={() => setSetupTab(value)}>{label}</button>)}
        </nav>
        {setupTab === "staff" && <>
          <h2>Staff access</h2>
          <p>Give each person their own account. Share temporary passwords privately; they must replace them on first sign-in.</p>
          <Table searchable rows={data.map((row: Row) => ({username: row.username, name: row.first_name,
            role: row.role, access: row.is_active ? 'Active' : 'Disabled',
            password: row.must_change_password ? 'Change required' : 'Set'}))}
            onOpen={row => {setAccountName(row.username); requestAnimationFrame(() => document.getElementById('staff-actions')?.scrollIntoView({block:'center', behavior:'smooth'}));}} />
          {form("Create staff account", "account.create", [
            field("name", "Full name"), field("username", "Username"),
            choice("role", "Role", [
              {value:"salesman",label:"Salesperson"}, {value:"admin",label:"Factory admin"},
              {value:"production",label:"Production supervisor"}, {value:"accountant",label:"Accountant (read only)"},
              {value:"owner",label:"Owner"}]),
            field("temporary_password", "Temporary password (12+ characters)", "", "password"),
          ])}
          {accountName && <section className="card" id="staff-actions" key={accountName}>
            <div className="section-heading"><h3>{accountName}</h3><button className="secondary" onClick={() => setAccountName(null)}>Close</button></div>
            {data.filter((row: Row) => row.username === accountName && row.id !== catalog.user_id).map((account: Row) => <React.Fragment key={account.id}>
              {form("Enable or disable account", "account.active", [
                choice("active", "Access", [{value:"true",label:"Enable"},{value:"false",label:"Disable"}]),
              ], {id:account.id}, d => ({active:d.active === "true"}))}
              {form("Reset temporary password", "account.reset", [
                field("temporary_password", "New temporary password", "", "password"),
              ], {id:account.id})}
            </React.Fragment>)}
          </section>}
        </>}
        {setupTab === "parties" && <>
          <h2>Customers</h2><Table searchable rows={catalog.customers.map((r: Row) =>
            ({code:r.code,name:r.name,state:r.state_code,gstin:r.gstin}))} />
          {form("Add customer", "master.customer", [field("code","Short code"),
            field("name","Customer name"),field("state_code","Two-digit GST state code"),
            field("gstin","GSTIN (15 characters)")])}
          <h2>Suppliers</h2><Table rows={catalog.suppliers.map((r: Row) =>
            ({code:r.code,name:r.name}))} />
          {form("Add supplier", "master.supplier", [field("code","Short code"),
            field("name","Supplier name")])}
        </>}
        {setupTab === "items" && <>
          <h2>Materials</h2>
          <p>Quantities are stored in g, ml or pieces. Receipts add stock after an item is created.</p>
          <Table rows={catalog.items.filter((r: Row) => r.category !== "finished")
            .map((r: Row) => ({code:r.code,name:r.name,type:r.category,unit:r.base_unit}))} />
          {form("Add material", "master.item", [field("code","Short code"),
            field("name","Material name"), choice("category","Type",[
              {value:"raw",label:"Ingredient"},{value:"packaging",label:"Packaging"}]),
            choice("base_unit","Base unit",[
              {value:"g",label:"Gram (g)"},{value:"ml",label:"Millilitre (ml)"},
              {value:"piece",label:"Piece"}])])}
          <h2>Products</h2><Table rows={catalog.skus.map((s: Row) => ({
            name:s.item__name,pack_size_g:s.pack_size_g,price_paise:s.price_paise,hsn:s.hsn}))} />
          {form("Add sellable product", "master.product", [field("code","Product code"),
            field("name","Product name"),field("pack_size_g","Pack size in grams","","number"),
            field("price_paise","Selling price in paise","","number"),
            field("hsn","HSN code"),field("carton_size","Packets per carton","20","number")])}
        </>}
        {setupTab === "recipes" && <>
          <h2>Production recipes</h2>
          <p>A new version affects future runs only. Shared recipes let another pack size use the same ingredients.</p>
          <Table rows={catalog.boms.map((b: Row) => ({product:b.sku__item__name,
            version:b.version,expected_packets:b.expected_packets}))} />
          {form("Add BOM version", "master.bom", [
            choice("sku","Product",asOptions(catalog.skus,"item__name")),
            field("expected_packets","Expected good packets per batch","","number"),
            choice("recipe","Ingredient recipe",[
              {value:"",label:"Create from raw quantities below"},
              ...catalog.recipes.map((r: Row) => ({value:r.id,label:r.code + " · v" + r.version}))]),
            ...catalog.items.filter((i: Row) => i.category === "raw")
              .map((i: Row) => field("raw_" + i.id,translate(i.name) + " · " + i.base_unit + " " + translate("per batch (0 to omit)"),"0","number")),
            ...catalog.items.filter((i: Row) => i.category === "packaging")
              .map((i: Row) => field("pack_" + i.id,translate(i.name) + " · " + translate("pieces per batch (0 to omit)"),"0","number")),
          ], {}, (d) => ({sku:d.sku,expected_packets:d.expected_packets,recipe:d.recipe || undefined,
            raw:collect(d,"raw_"),packaging:collect(d,"pack_")}))}
        </>}
      </>}
      {page === "prices" &&
        admin &&
        form("Save customer price", "price", [
          customer,
          sku,
          field("price_paise", "Price in paise", "", "number"),
          field("label", "Scheme label", "Customer price"),
        ])}
      {page === "visits" && (
        <>
          {sales && (
            <VisitForm
              customers={catalog.customers}
              submit={(d, key) => command("visit", d, key)}
            />
          )}
          {Array.isArray(data) && <Table rows={data} />}
        </>
      )}
      {page === "reports" && (
        <>
          <div className="filters">
            <div className="report-picker" role="group" aria-label="Report">
              {Object.entries(catalog.reports).filter(([k]) => reports || k === "customers").map(([k,v]) =>
                <button className="secondary" key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>{translate(String(v))}</button>)}
            </div>
            <label>
              From
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              Through / as of
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
          </div>
          <button
            onClick={() =>
              download(
                `/reports/${kind}?start=${start}&end=${end}&format=csv`,
                kind + ".csv",
              )
            }
          >
            Export CSV
          </button>
          <button
            onClick={() =>
              download(
                `/reports/${kind}?start=${start}&end=${end}&format=pdf`,
                kind + ".pdf",
              )
            }
          >
            Export PDF
          </button>
          {reports && (
            <button
              onClick={() =>
                download(
                  `/reports/tally?start=${start}&end=${end}`,
                  "tally.zip",
                )
              }
            >
              Tally XML
            </button>
          )}
          {data && (
            <>
              <h2>{data.title}</h2>
              <Table
                rows={data.rows.map((row: any[]) =>
                  Object.fromEntries(
                    data.headers.map((header: string, i: number) => [
                      header,
                      row[i],
                    ]),
                  ),
                )}
              />
            </>
          )}
        </>
      )}
      {page === "dashboard" && data && <>
        <div className="metric-grid">
          <article><span>{translate("Orders today")}</span><strong>{data.orders_today}</strong></article>
          <article><span>{translate("Outstanding")}</span><strong>{money(data.outstanding)}</strong></article>
          <article><span>{translate("Variance alerts")}</span><strong>{data.flagged_runs}</strong></article>
          <article><span>{translate("Production cost")}</span><strong>{money(data.run_cost)}</strong></article>
        </div>
        <h2>Stock</h2><Table rows={Object.entries(data.stock).map(([code,value]) => ({code, name: catalog.items.find((item: Row) => item.code === code)?.name || code,...value as Row}))} searchable unitFor={stockUnit} />
        <h2>Products</h2><Table rows={data.products.map((product: Row) => ({name:product.name, good_packets:product.good,
          total_paise:product.cost, unit_cost:product.unit_cost, margin:product.margin}))} />
        <h2>Reorder alerts</h2><Table rows={data.reorder_alerts} />
        <h2>Collection follow-ups</h2><Table rows={data.due_followups} />
      </>}
      {page === "offline" && <Offline catalog={catalog} token={token} />}
      {!data && !error && <p role="status">Loading…</p>}
    </>
  );
}
