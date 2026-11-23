// Catch untranslated static UI copy before a release.
const fs = require("node:fs");
const path = require("node:path");
const ts = require("../frontend/node_modules/typescript");
const root = path.join(__dirname, "..", "frontend", "src");
const catalog = require(path.join(root, "translations.json"));
const languages = ["ta", "hi", "mr"];
const exempt = new Set(["Order-to-Audit", "ORDER-TO-AUDIT"]);
const labels = new Map([["field", 1], ["choice", 1], ["form", 0],
  ["setMessage", 0], ["setError", 0], ["Error", 0], ["translate", 0]]);
const used = new Set();

function collect(source, node) {
  if (ts.isJsxText(node)) {
    const text = node.getText(source).replace(/\s+/g, " ").trim();
    if (/[A-Za-z]/.test(text)) used.add(text);
  }
  if ((ts.isCallExpression(node) || ts.isNewExpression(node)) &&
      ts.isIdentifier(node.expression) && labels.has(node.expression.text)) {
    const argument = node.arguments?.[labels.get(node.expression.text)];
    if (argument && ts.isStringLiteral(argument)) used.add(argument.text);
  }
  if (ts.isPropertyAssignment(node) && node.name.getText(source) === "label" &&
      ts.isStringLiteral(node.initializer)) used.add(node.initializer.text);
  if (ts.isJsxAttribute(node) && ["aria-label", "placeholder", "title"].includes(node.name.text) &&
      node.initializer && ts.isStringLiteral(node.initializer)) used.add(node.initializer.text);
  ts.forEachChild(node, child => collect(source, child));
}

for (const name of ["main", "Workspace", "Offline", "VisitForm"]) {
  const file = path.join(root, name + ".tsx");
  const source = ts.createSourceFile(file, fs.readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  collect(source, source);
}
for (const generated of ["Price (₹)", "Amount (₹)", "Total value (₹)",
  "Positive adjustment value (₹)", "Selling price (₹)", "Value (₹)",
  "(exact)"]) used.add(generated);
const all = new Set([...used, ...languages.flatMap(language => Object.keys(catalog[language]))]);
const missing = [...all].filter(key => key && !exempt.has(key) &&
  languages.some(language => !catalog[language][key])).sort();
const damaged = languages.flatMap(language => Object.entries(catalog[language])
  .filter(([, value]) => /\?\?|\uFFFD/.test(value)).map(([key]) => `${language}: ${key}`));
const checked = [...used].filter(key => key && !exempt.has(key));
if (missing.length || damaged.length) {
  console.error("Missing translations:", missing, "Damaged encoding:", damaged);
  process.exitCode = 1;
} else {
  console.log(`Translation coverage: ${checked.length} UI strings × ${languages.length} languages`);
}
