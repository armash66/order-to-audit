import React, { useEffect, useState } from "react";
import { useLocalize, useTranslate } from "./language";

// Native radios expose short choices; a search narrows long lists without hiding selection.
export function ChoiceField({field, options, resetKey}: {field: {name: string; label: string; value?: string; optional?: boolean}; options: {value: string; label: string}[]; resetKey: string}) {
  const translate = useTranslate(), localize = useLocalize();
  const [query, setQuery] = useState("");
  const [value, setValue] = useState(field.value ?? options[0]?.value ?? "");
  useEffect(() => {setValue(field.value ?? options[0]?.value ?? ""); setQuery("");}, [resetKey]);
  const selected = options.find(option => option.value === value);
  const visible = options.filter(option => option.value === value || translate(option.label).toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  return localize(<fieldset className="choice-field" data-field={field.name}>
    <legend>{translate(field.label)}</legend>
    {options.length > 6 && <label className="choice-search">Search choices
      <input type="search" value={query} onChange={event => setQuery(event.target.value)} />
    </label>}
    <div className={options.length > 6 ? "choice-options choice-scroll" : "choice-options"}>
      {visible.map(option => <label key={option.value} className={value === option.value ? "chosen" : ""}>
        <input type="radio" name={field.name} value={option.value} checked={value === option.value}
          required={!field.optional} onChange={() => setValue(option.value)} />{translate(option.label)}
      </label>)}
    </div>
    {!options.length && <p>No records yet.</p>}
    {query && visible.length === (selected ? 1 : 0) && !options.some(option => translate(option.label).toLocaleLowerCase().includes(query.toLocaleLowerCase())) && <p>No matching records.</p>}
  </fieldset>);
}
