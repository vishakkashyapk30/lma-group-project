// Breadcrumb: plain links separated by a chevron. The last item is the current page.
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Fragment, type ReactElement } from "react";
import { MorphTarget } from "@/components/motion/Morph";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
  /** Render in the mono face (ids). */
  mono?: boolean;
  /** Morph name: a title recorded under this name before the navigation moves into this crumb (components/motion/Morph). */
  share?: string;
}

export function Breadcrumb({ items, className }: { items: readonly Crumb[]; className?: string }): ReactElement {
  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0", className)}>
      <ol className="flex min-w-0 items-center gap-1 text-sm">
        {items.map((c, i) => {
          const last = i === items.length - 1;
          return (
            <Fragment key={`${c.label}-${i}`}>
              {i > 0 ? <ChevronRight aria-hidden className="size-3.5 shrink-0 text-ink-muted" /> : null}
              <li className={cn("min-w-0", last ? "truncate" : "shrink-0")}>
                {c.href && !last ? (
                  <Link href={c.href} className={cn("rounded-sm text-ink-soft no-underline hover:text-ink hover:underline", c.mono && "font-mono text-xs")}>
                    {c.label}
                  </Link>
                ) : (
                  <MaybeShared name={c.share}>
                    <span aria-current={last ? "page" : undefined} className={cn("block truncate", last ? "font-semibold text-ink" : "text-ink-soft", c.mono && "font-mono text-xs")}>
                      {c.label}
                    </span>
                  </MaybeShared>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}

function MaybeShared({ name, children }: { name?: string; children: ReactElement }): ReactElement {
  return name ? <MorphTarget name={name} className="min-w-0 truncate align-bottom">{children}</MorphTarget> : children;
}
