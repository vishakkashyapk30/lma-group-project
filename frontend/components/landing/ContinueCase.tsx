"use client";
// Header action on the landing page: "Continue: <last case>" for someone coming back, "Open workspace" otherwise. The
// remembered case is read after hydration; the button keeps a fixed minimum width so swapping the label does not move
// the header.
import Link from "next/link";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { useLastCase } from "@/lib/lastCase";

export function ContinueCase(): ReactElement {
  const last = useLastCase();
  if (!last) {
    return (
      <Button asChild className="lift min-w-[9.5rem]">
        <Link href="/cases" className="no-underline">Open workspace</Link>
      </Button>
    );
  }
  const name = `Continue: ${last.title}${last.stageLabel ? `, at ${last.stageLabel}` : ""}`;
  return (
    <span className="flex min-w-0 items-center gap-3">
      <Link href="/cases" className="link-draw hidden whitespace-nowrap text-sm text-ink-soft hover:text-ink md:inline">All cases</Link>
      <Button asChild className="lift min-w-[9.5rem] max-w-[13rem] sm:max-w-[22rem]">
        <Link href={`/case/${last.id}`} data-testid="continue-case" aria-label={name} title={name} className="no-underline">
          <span className="truncate">Continue: {last.title}</span>
        </Link>
      </Button>
    </span>
  );
}
