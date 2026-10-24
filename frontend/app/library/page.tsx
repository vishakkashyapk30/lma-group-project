// `/library` Precedent search, citation graph and the IPC/BNS bridge (plan §13.5).
import type { Metadata } from "next";
import { LibraryPage } from "@/components/library/LibraryPage";

export const metadata: Metadata = { title: "Precedent library" };

export default function Page() {
  return <LibraryPage />;
}
