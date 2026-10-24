"use client";
// Precedent library page: search, citation graph, IPC<->BNS bridge. The graph (React Flow) loads lazily.
import dynamic from "next/dynamic";
import { useState, type ReactElement } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger, Skeleton } from "@/components/ui";
import { PageHeader } from "@/components/common/PageHeader";
import { cn } from "@/lib/utils";
import { BridgeView } from "./BridgeView";
import { PrecedentSearch } from "./PrecedentSearch";

const CitationGraph = dynamic(() => import("./CitationGraph"), {
  ssr: false,
  loading: () => <Skeleton className="h-[32rem]" aria-label="Loading the citation graph" />,
});

export interface LibraryPageProps {
  className?: string;
}

export function LibraryPage({ className }: LibraryPageProps): ReactElement {
  const [tab, setTab] = useState("search");
  const [docId, setDocId] = useState("DLHC-2022-1187");
  const [bridgeRef, setBridgeRef] = useState("IPC 420");

  return (
    <div className={cn("mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10", className)}>
      <PageHeader
        title="Precedent library"
        description="Search how courts reasoned, follow who cited whom and whether the law is still good, and compare an IPC section with its BNS successor. Nothing here predicts an outcome."
      />
      <Tabs value={tab} onValueChange={setTab} className="mt-5">
        <TabsList aria-label="Library views">
          <TabsTrigger value="search">Precedent search</TabsTrigger>
          <TabsTrigger value="graph">Citation graph</TabsTrigger>
        </TabsList>
        <TabsContent value="search" className="pt-5">
          <PrecedentSearch
            onOpenGraph={(id) => { setDocId(id); setTab("graph"); }}
            onOpenBridge={(r) => {
              setBridgeRef(r);
              document.getElementById("bridge")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
            }}
          />
        </TabsContent>
        <TabsContent value="graph" className="pt-5">
          <CitationGraph docId={docId} onSelectDoc={setDocId} />
        </TabsContent>
      </Tabs>
      {/* The bridge stays on the page next to the search: counsel compares sections while reading precedents. */}
      <section id="bridge" aria-labelledby="bridge-heading" className="mt-10 scroll-mt-20 border-t border-line pt-6">
        <h2 id="bridge-heading" className="font-display text-xl font-semibold">IPC ↔ BNS bridge</h2>
        <p className="mb-4 mt-1 max-w-prose text-sm text-ink-soft">The old section beside the new one, with the changed words marked.</p>
        <BridgeView initialRef={bridgeRef} />
      </section>
    </div>
  );
}

export default LibraryPage;
