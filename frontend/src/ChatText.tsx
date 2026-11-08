// The assistant's words in either screen: bold text, and each policy citation by its title. The customer sees the
// title, with the ID on hover; the staff member sees the ID beside it, to trace a statement to its section.

import { Fragment, useEffect, useState } from "react";

import { api } from "./api";
import { messageParts } from "./messageText";

let loading: Promise<ReadonlyMap<string, string>> | null = null;

function loadTitles(): Promise<ReadonlyMap<string, string>> {
  loading ??= api
    .policy()
    .then((policy) => new Map(policy.sections.map((section) => [section.citation, section.title])))
    .catch((error: unknown) => {
      loading = null; // read again next time; until then, citations show as written
      throw error;
    });
  return loading;
}

/** The titles of the policy the server enforces, read once; empty until read, or if the read fails. */
export function usePolicyTitles(): ReadonlyMap<string, string> {
  const [titles, setTitles] = useState<ReadonlyMap<string, string>>(new Map());
  useEffect(() => {
    let current = true;
    loadTitles().then(
      (read) => current && setTitles(read),
      () => {},
    );
    return () => {
      current = false;
    };
  }, []);
  return titles;
}

export function ChatText(props: { text: string; titles: ReadonlyMap<string, string>; viewer: "customer" | "staff" }) {
  return (
    <>
      {messageParts(props.text, props.titles).map((part, index) => {
        const shown =
          part.kind === "text" ? (
            part.text
          ) : props.viewer === "staff" ? (
            <span className="citation">
              Policy: {part.title} <code>{part.citation}</code>
            </span>
          ) : (
            <span className="citation" title={part.citation}>
              Policy: {part.title}
            </span>
          );
        return part.strong ? <strong key={index}>{shown}</strong> : <Fragment key={index}>{shown}</Fragment>;
      })}
    </>
  );
}
