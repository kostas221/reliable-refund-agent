// How the assistant's words are shown (docs/screens.md): the bold marks it writes are shown as bold text, and a policy
// citation as its section's title from the policy the server enforces. The stored text is never changed, and nothing
// in it is read as markup: the parts are plain strings that React escapes. Pure functions, tested in
// messageText.test.ts.

export type Part =
  | { kind: "text"; text: string; strong: boolean }
  | { kind: "citation"; citation: string; title: string; strong: boolean };

// A pair of bold marks on one line around text that starts and ends with a visible character, as in Markdown:
// **like this**, but not "2 ** 3".
const BOLD = /\*\*(?=\S)([^*\n]*?\S)\*\*/g;
// A citation ID as the policy writes it: refund-policy/v2/return.
const CITATION = /[a-z]+(?:-[a-z]+)*\/v[0-9]+\/[a-z]+(?:-[a-z]+)*/g;

/** The message cut into plain text, bold text and citations the policy holds. An ID it does not hold stays text. */
export function messageParts(text: string, titles: ReadonlyMap<string, string>): Part[] {
  const parts: Part[] = [];
  let at = 0;
  for (const bold of text.matchAll(BOLD)) {
    citations(text.slice(at, bold.index), false, titles, parts);
    citations(bold[1]!, true, titles, parts);
    at = bold.index + bold[0].length;
  }
  citations(text.slice(at), false, titles, parts);
  return parts;
}

function citations(text: string, strong: boolean, titles: ReadonlyMap<string, string>, parts: Part[]): void {
  let at = 0;
  for (const found of text.matchAll(CITATION)) {
    const title = titles.get(found[0]);
    if (title === undefined) continue;
    plain(text.slice(at, found.index), strong, parts);
    parts.push({ kind: "citation", citation: found[0], title, strong });
    at = found.index + found[0].length;
  }
  plain(text.slice(at), strong, parts);
}

/** Adds plain text, joined to the part before it when that one is plain text of the same weight. */
function plain(text: string, strong: boolean, parts: Part[]): void {
  if (!text) return;
  const last = parts.at(-1);
  if (last?.kind === "text" && last.strong === strong) last.text += text;
  else parts.push({ kind: "text", text, strong });
}
