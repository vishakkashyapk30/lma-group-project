// `/cases` Cause list: today's matters with rights chips, urgent first (plan §13.3).
import type { Metadata } from "next";
import { CauseList } from "@/components/cases/CauseList";

export const metadata: Metadata = { title: "Cause list" };

export default function Page() {
  return <CauseList />;
}
