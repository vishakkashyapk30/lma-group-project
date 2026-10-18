// `/about` The six agents, how it works and its limits (plan §13.3).
import type { Metadata } from "next";
import { AboutPage } from "@/components/about/AboutPage";

export const metadata: Metadata = { title: "About" };

export default function Page() {
  return <AboutPage />;
}
