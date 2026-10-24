// `/cases` Cases: every matter, urgent first.
import type { Metadata } from "next";
import { CauseList } from "@/components/cases/CauseList";

export const metadata: Metadata = { title: "Cases" };

export default function Page() {
  return <CauseList />;
}
