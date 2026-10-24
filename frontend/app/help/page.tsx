// `/help` Shortcuts, how to start, and where to read about method and limits.
import type { Metadata } from "next";
import { HelpPage } from "@/components/help/HelpPage";

export const metadata: Metadata = { title: "Help" };

export default function Page() {
  return <HelpPage />;
}
