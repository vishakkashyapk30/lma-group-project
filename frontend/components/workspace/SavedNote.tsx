"use client";
// A quiet "Saved" after an edit. Edits save as they are made; this only says so, for a few seconds.
import { useEffect, useState, type ReactElement } from "react";
import { useWorkspace } from "@/lib/workspace";

export function SavedNote(): ReactElement {
  const { savedAt } = useWorkspace();
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (savedAt === null) return;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), 3000);
    return () => clearTimeout(t);
  }, [savedAt]);
  return (
    <span role="status" aria-live="polite" data-testid="saved-note" className="min-w-[3.5rem] text-sm text-ink-muted">
      {visible ? "Saved" : ""}
    </span>
  );
}

export default SavedNote;
