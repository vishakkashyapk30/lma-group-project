// Landing footer: the draft disclaimer, free legal aid for the public (NALSA 15100), Help and About, and the Supreme Court motto.
import Link from "next/link";
import type { ReactElement } from "react";

export function Footer(): ReactElement {
  return (
    <footer className="bg-parchment-deep" data-testid="site-footer">
      <div className="mx-auto flex max-w-[76rem] flex-col gap-3 px-4 py-8 text-sm text-ink-soft sm:px-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p>AI-generated drafts for counsel. Not legal advice.</p>
          <p className="mt-1">Free legal aid for the public: <a href="tel:15100" className="link-draw font-medium" data-rest>NALSA 15100</a></p>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 md:justify-end">
          <Link href="/help" className="link-draw text-ink-soft hover:text-maroon">Help</Link>
          <Link href="/about" className="link-draw text-ink-soft hover:text-maroon">About and limits</Link>
          <p lang="hi" className="text-xs text-ink-muted">यतो धर्मस्ततो जयः</p>
        </div>
      </div>
    </footer>
  );
}
