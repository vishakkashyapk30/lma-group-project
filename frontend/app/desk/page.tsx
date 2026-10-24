// `/desk` Pairokar's batch desk: triage board (plan §11, §13.5).
import type { Metadata } from "next";
import { DeskPage } from "@/components/desk/DeskPage";

export const metadata: Metadata = { title: "Batch desk" };

export default function Page() {
  return <DeskPage />;
}
