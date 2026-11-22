import React, { useEffect, useState } from "react";
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

// Paise conversion uses decimal strings and BigInt only, including negative adjustments.
export function money(value: unknown): string {
  if (value === null || value === undefined) return "Unknown";
  const number = BigInt(String(value));
  const absolute = number < 0n ? -number : number;
  return `${number < 0n ? "−" : ""}₹${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}

function Table({ rows, onOpen }: { rows: Row[]; onOpen?: (row: Row) => void }) {
  const localize = useLocalize();
  if (!rows.length) return localize(<p>No records yet.</p>);
  const columns = Object.keys(rows[0]);
  return localize(
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((key) => (
              <th key={key}>{key.replaceAll("_", " ")}</th>
            ))}
            {onOpen && <th>Action</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((key) => (
                <td key={key}>{display(row[key], key)}</td>
              ))}
              {onOpen && (
                <td>
                  <button onClick={() => onOpen(row)}>Open</button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function display(value: any, key = ""): React.ReactNode {
  if (value === null || value === undefined) return "—";
  if (key.endsWith("paise") && typeof value === "string") return money(value);
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
      <dl>
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
}: {
  title: string;
  fields: Field[];
  submit: (data: Row, key: string) => Promise<void>;
  customerPrices?: (id: string) => Promise<Row[]>;
}) {
  const translate = useTranslate();
  const localize = useLocalize();
  const errorText = useErrorText();
  const [prices,setPrices]=useState<Row[]>([]);
  async function refreshPrices(id:string){if(customerPrices)try{setPrices(await customerPrices(id));}catch{setPrices([]);}}
  useEffect(()=>{const id=fields.find(f=>f.name==='customer')?.options?.[0]?.value;if(id)refreshPrices(id);},[]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [key, setKey] = useState(crypto.randomUUID());
  return localize(
    <details className="card">
      <summary>{translate(title)}</summary>
      <form
        onChange={event=>{const target=event.target as HTMLInputElement;if(target.name==='customer')refreshPrices(target.value);}}
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
            const customerId=fields.find(f=>f.name==='customer')?.options?.[0]?.value;if(customerId)refreshPrices(customerId);
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {fields.map((f) => (
          <label key={f.name}>
            {translate(f.label)}
            {f.options ? (
              <select
                aria-label={translate(f.label)}
                name={f.name}
                defaultValue={f.value}
              >
                {f.options.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                aria-label={translate(f.label)}
                name={f.name}
                defaultValue={f.value}
                type={f.type || "text"}
                required={!f.optional}
              />
            )}
          </label>
        ))}
        {error && <p role="alert">{errorText(error)}</p>}
        {prices.length>0&&<div className="notice">Prices before GST:{prices.map(price=><p key={price.sku_id}>{price.name}: {money(price.price_paise)} · {price.label}</p>)}</div>}
        <button disabled={busy}>{busy ? "Saving…" : translate(title)}</button>
      </form>
    </details>
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
    setNotice("Saved successfully.");
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
      <LanguageSwitch />
      <nav className="tabs" aria-label="Workspace">
        {[{heading:'Daily work',names:dailyMenu},{heading:'Tools & setup',names:toolsMenu}].map((group) =>
          <div className="nav-group" key={group.heading}>
            <span>{translate(group.heading)}</span>
            {group.names.map((name) => <button key={name}
              aria-current={page === name ? "page" : undefined}
              onClick={() => navigate(name)}>
              {translate(name[0].toUpperCase() + name.slice(1))}</button>)}
          </div>)}
      </nav>
      <h1>
        {translate(page[0].toUpperCase() + page.slice(1))}
        {selected && " #" + selected}
      </h1>
      {selected && (
        <button onClick={() => setSelected(null)}>← Back to list</button>
      )}
      {error && <p role="alert">{errorText(error)}</p>}
      {notice && <p role="status" className="notice">{notice}</p>}
      {page === "orders" && !selected && (
        <>
          {sales &&
            form(
              "Submit order",
              "order.create",
              [
                customer,
                dateField,
                ...catalog.skus.map((s: Row) =>
                  field(
                    "qty_" + s.id,
                    translate(s["item__name"]) + " · " + translate("packets (0 to omit)"),
                    "0",
                    "number",
                  ),
                ),
              ],
              {},
              (d) => ({
                customer: d.customer,
                date: d.date,
                quantities: collect(d, "qty_"),
              }),
            )}
          {Array.isArray(data) && (
            <Table rows={data} onOpen={(row) => setSelected(row.id)} />
          )}
        </>
      )}
      {page === "orders" && selected && data && !Array.isArray(data) && (
        <>
          <h2>
            {data.customer} · {translate(data.status)}
          </h2>
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
                      "price_" + line.id,
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
                        [d["qty_" + line.id], d["price_" + line.id]],
                      ]),
                    ),
                  }),
                )}
            </>
          )}
          {data.invoice && (
            <section className="card">
              <h2>Invoice {data.invoice.number}</h2>
              <p>
                Taxable {money(data.invoice.taxable_paise)} · CGST{" "}
                {money(data.invoice.cgst_paise)} · SGST{" "}
                {money(data.invoice.sgst_paise)} · IGST{" "}
                {money(data.invoice.igst_paise)}
              </p>
              <h3>
                Total {money(data.invoice.total_paise)} · Outstanding{" "}
                {money(data.invoice.outstanding)}
              </h3>
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
                "Quantity in base units (g / ml / piece)",
                "",
                "number",
              ),
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
          {Array.isArray(data) && (
            <Table rows={data} onOpen={(row) => setSelected(row.id)} />
          )}
        </>
      )}
      {page === "production" && selected && data && !Array.isArray(data) && (
        <>
          <h2>
            {data.name} · {translate(data.state)}
          </h2>
          {data.state === "draft" &&
            form(
              "Issue raw materials",
              "production.issue",
              data.standards
                .filter((s: Row) => s.stage === "raw")
                .map((s: Row) =>
                  field(
                    "qty_" + s.item__code,
                    translate(s.item__name) + " (" + s.item__base_unit + ")",
                    s.quantity,
                    "number",
                  ),
                ),
              { id: selected },
              (d) => ({ actual: collect(d, "qty_", true) }),
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
          <section className="card">
            <h2>Variance and costing</h2>
            {display(data.report)}
          </section>
        </>
      )}
      {page === "stock" && Array.isArray(data) && (
        <Table rows={data} onOpen={(row) => setSelected(row.code)} />
      )}
      {page === "stock" && selected && data && !Array.isArray(data) && (
        <>
          <h2>{data.item.name}</h2>
          <Table rows={data.movements} onOpen={async (row) => {
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
          <Table rows={data.map((row: Row) => ({username: row.username, name: row.first_name,
            role: row.role, access: row.is_active ? 'Active' : 'Disabled',
            password: row.must_change_password ? 'Change required' : 'Set'}))} />
          {form("Create staff account", "account.create", [
            field("name", "Full name"), field("username", "Username"),
            choice("role", "Role", [
              {value:"salesman",label:"Salesperson"}, {value:"admin",label:"Factory admin"},
              {value:"production",label:"Production supervisor"}, {value:"accountant",label:"Accountant (read only)"},
              {value:"owner",label:"Owner"}]),
            field("temporary_password", "Temporary password (12+ characters)", "", "password"),
          ])}
          {form("Enable or disable account", "account.active", [
            choice("id", "Account", data.filter((r: Row) => r.id !== catalog.user_id)
              .map((r: Row) => ({value:r.id,label:r.username + " · " + translate(r.role)}))),
            choice("active", "Access", [{value:"true",label:"Enable"},{value:"false",label:"Disable"}]),
          ], {}, (d) => ({id:d.id,active:d.active === "true"}))}
          {form("Reset temporary password", "account.reset", [
            choice("id", "Account", data.filter((r: Row) => r.id !== catalog.user_id)
              .map((r: Row) => ({value:r.id,label:r.username}))),
            field("temporary_password", "New temporary password", "", "password"),
          ])}
        </>}
        {setupTab === "parties" && <>
          <h2>Customers</h2><Table rows={catalog.customers.map((r: Row) =>
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
            <label>
              Report
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                {Object.entries(catalog.reports)
                  .filter(([k]) => reports || k === "customers")
                  .map(([k, v]) => (
                    <option key={k} value={k}>
                      {String(v)}
                    </option>
                  ))}
              </select>
            </label>
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
      {page === "dashboard" && data && display(data)}
      {page === "offline" && <Offline catalog={catalog} token={token} />}
      {!data && !error && <p role="status">Loading…</p>}
    </>
  );
}
