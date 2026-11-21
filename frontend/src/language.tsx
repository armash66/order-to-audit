import { createContext, useContext } from "react";
export const LanguageContext = createContext<Record<string, string>>({});
export function useTranslate() {
  const words = useContext(LanguageContext);
  return (label: string) => words[label] || label;
}
