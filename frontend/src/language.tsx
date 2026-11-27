import React, { createContext, useContext, useEffect, useState } from "react";
import catalog from "./translations.json";

export type Language = "en" | "ta" | "hi" | "mr";
const choices: Language[] = ["en", "ta", "hi", "mr"];
type LanguageState = { language: Language; setLanguage: (value: Language) => void };
const LanguageContext = createContext<LanguageState>({ language: "en", setLanguage: () => {} });

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    const saved = localStorage.getItem("ota-language") as Language;
    return choices.includes(saved) ? saved : "en";
  });
  useEffect(() => {
    localStorage.setItem("ota-language", language);
    document.documentElement.lang = language;
  }, [language]);
  return <LanguageContext.Provider value={{ language, setLanguage }}>{children}</LanguageContext.Provider>;
}

export function useLanguage() { return useContext(LanguageContext); }

export function useTranslate() {
  const { language } = useLanguage();
  const words: Record<string, string> = catalog[language];
  return (label: string) => {
    const exact = words[label] || words[label[0]?.toUpperCase() + label.slice(1)];
    return exact || (label.includes("FLAG") ? label.replace(/\bFLAG\b/g, words.FLAG || "FLAG") : label);
  };
}

export function useErrorText() {
  const translate = useTranslate();
  const { language } = useLanguage();
  return (message: string) => {
    if (language === "en") return message;
    const localized = translate(message);
    return localized === message
      ? translate("Could not complete this action. Check the form and try again.")
      : localized;
  };
}

export function LanguageSwitch() {
  const { language, setLanguage } = useLanguage();
  const translate = useTranslate();
  return <fieldset className="language-picker" data-testid="language-switch">
    <legend>{translate("Language")}</legend>
    {([ ["en", "English"], ["ta", "தமிழ்"], ["hi", "हिन्दी"], ["mr", "मराठी"] ] as const).map(([code, label]) =>
      <button key={code} type="button" data-language={code} aria-pressed={language === code} onClick={() => setLanguage(code)}>{label}</button>)}
  </fieldset>;
}

// Translate known screen copy and seed names, leaving unknown data values intact.
export function useLocalize() {
  const translate = useTranslate();
  function localize(node: React.ReactNode): React.ReactNode {
    if (typeof node === "string") {
      const match = node.match(/^(\s*)(.*?)(\s*)$/s);
      return match ? match[1] + translate(match[2].replace(/\s+/g, " ")) + match[3] : node;
    }
    if (Array.isArray(node)) return node.map(localize);
    if (!React.isValidElement(node)) return node;
    const props = node.props as Record<string, unknown>;
    const changes: Record<string, unknown> = {};
    for (const name of ["aria-label", "title", "placeholder", "alt"])
      if (typeof props[name] === "string") changes[name] = translate(props[name]);
    if (props.children !== undefined) changes.children = localize(props.children as React.ReactNode);
    return React.cloneElement(node, changes);
  }
  return localize;
}
