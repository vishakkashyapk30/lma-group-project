"use client";
// New case: a title is optional. Opened from the top bar, the command palette and the Cases page.
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactElement } from "react";
import {
  Button, Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, Input, useToast,
} from "@/components/ui";
import { useShell } from "@/components/shell/ShellProvider";
import { createCase } from "@/lib/api";
import { errorMessage } from "@/lib/errors";

export function NewCaseDialog(): ReactElement {
  const router = useRouter();
  const toast = useToast();
  const { newCaseOpen, setNewCaseOpen } = useShell();
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const created = await createCase(title.trim() || null);
      setNewCaseOpen(false);
      setTitle("");
      toast({ title: "Case created", description: created.title });
      router.push(`/case/${created.case_id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open={newCaseOpen} onOpenChange={(o) => { setNewCaseOpen(o); if (!o) setError(null); }}>
      <DialogContent size="sm">
        <form onSubmit={onCreate}>
          <DialogHeader>
            <DialogTitle>New case</DialogTitle>
            <DialogDescription>Use initials or a short reference, not the client&apos;s full name.</DialogDescription>
          </DialogHeader>
          <DialogBody>
            <label htmlFor="new-case-title" className="mb-1 block text-sm font-medium">Case title (optional)</label>
            <Input id="new-case-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. State v. R.K., bail application" autoFocus />
            {error ? <p role="alert" className="mt-2 text-sm text-sindoor">{error}</p> : null}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setNewCaseOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={creating}>{creating ? "Creating" : "Create and open"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
