// `/about` How it works and its limits.
import type { Metadata } from "next";
import { AboutPage } from "@/components/about/AboutPage";

export const metadata: Metadata = { title: "About" };

export default function Page() {
  return <AboutPage />;
}
