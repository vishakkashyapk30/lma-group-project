"use client";
// Settings: which server this window talks to, and the model, privacy and data settings that server runs with (GET /healthz).
// The settings are chosen when the server starts, so this page shows them and says where each one is set.
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactElement, type ReactNode } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { API_BASE, API_SETTING, getApiMode, getDemoReason, getServerStatus, unreachableMessage } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { ServerStatus } from "@/lib/types";

const MODELS: Record<string, string> = {
  offline: "Built-in stand-ins. No language model runs, so drafts are placeholders. For trying the product and for tests.",
  real: "Real models only. A model that cannot run stops the work with an error.",
  auto: "Real models where they are installed, otherwise an error for that step.",
};

const LLM: Record<string, string> = {
  offline: "Built-in stand-in for every agent.",
  local: "Open-weight models on this machine or the cluster.",
  sarvam: "Sarvam, a hosted service, within its spending cap and the privacy settings below.",
  openai: "OpenAI, a hosted service, within its spending cap and the privacy settings below.",
};

const PRIVACY: Record<string, string> = {
  off: "Off. Nothing leaves this machine.",
  public: "Public data only. Case text is never sent.",
  pseudonymised: "Pseudonymised text. Client text is sent only after names and identifiers are replaced and checked.",
  consented: "Consented. Raw pages and audio may be sent, only for a case where consent is recorded.",
};

const SETTING: Record<string, string> = {
  live: "Server only. If the server does not answer, pages show an error and never sample data.",
  auto: "Server, switching to the sample cases if it does not answer. Meant for development.",
  demo: "Sample cases only. Nothing is sent to a server.",
};

function Block({ id, title, children }: { id: string; title: string; children: ReactNode }): ReactElement {
  return (
    <section aria-labelledby={id} className="mt-8 border-t border-line pt-5">
      <h2 id={id} className="mb-3 font-display text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Rows({ rows }: { rows: { label: string; value: ReactNode; set?: string; atBuild?: boolean }[] }): ReactElement {
  return (
    <dl className="m-0 divide-y divide-line border-y border-line">
      {rows.map((r) => (
        <div key={r.label} className="grid gap-1 py-2.5 sm:grid-cols-[12rem_1fr]">
          <dt className="font-medium text-ink">{r.label}</dt>
          <dd className="m-0 text-sm text-ink-soft">
            {r.value}
            {r.set ? <span className="mt-0.5 block text-xs text-ink-muted">Set with <code>{r.set}</code> {r.atBuild ? "when this app is built" : "when the server starts"}.</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function describe(table: Record<string, string>, value: string | null | undefined): string {
  if (!value) return "Not reported by the server.";
  return table[value] ?? value;
}

type Load = { state: "loading" } | { state: "demo" } | { state: "down" } | { state: "error"; message: string } | { state: "ok"; status: ServerStatus };

export function SettingsPage(): ReactElement {
  const [load, setLoad] = useState<Load>({ state: "loading" });

  const check = useCallback(async () => {
    setLoad({ state: "loading" });
    if (getApiMode() === "demo") {
      setLoad({ state: "demo" });
      return;
    }
    try {
      const status = await getServerStatus();
      setLoad(status ? { state: "ok", status } : getApiMode() === "demo" ? { state: "demo" } : { state: "down" });
    } catch (e) {
      setLoad({ state: "error", message: errorMessage(e) });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  const status = load.state === "ok" ? load.status : null;
  const connection =
    load.state === "loading" ? "Checking…"
      : load.state === "ok" ? "Connected."
        : load.state === "demo" ? `Not connected: working on the built-in sample cases${getDemoReason() ? ` (${getDemoReason()})` : ""}.`
          : load.state === "down" ? unreachableMessage()
            : load.message;

  return (
    <div className="mx-auto max-w-content px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Settings"
        description="The server this window uses, and the model, privacy and data settings that server runs with."
        actions={<Button variant="secondary" onClick={() => void check()} disabled={load.state === "loading"}>Check again</Button>}
      />
      <div className="max-w-3xl" aria-live="polite">
        <Block id="server" title="Server">
          <Rows rows={[
            { label: "Address", value: API_BASE ?? "None set", set: "NEXT_PUBLIC_API_BASE", atBuild: true },
            { label: "When it does not answer", value: describe(SETTING, API_SETTING), set: "NEXT_PUBLIC_API_MODE", atBuild: true },
            { label: "Status", value: connection },
          ]} />
        </Block>

        {status ? (
          <>
            <Block id="models" title="Models">
              <Rows rows={[
                { label: "Model mode", value: describe(MODELS, status.models), set: "VS_MODELS" },
                { label: "Language model", value: status.llm_backend ? describe(LLM, status.llm_backend) : "As configured for each agent in configs/models.yaml.", set: "VS_LLM_BACKEND" },
              ]} />
            </Block>

            <Block id="privacy" title="Privacy">
              <Rows rows={[
                { label: "External services", value: describe(PRIVACY, status.external), set: "VS_EXTERNAL" },
                { label: "Sarvam", value: describe(PRIVACY, status.sarvam), set: "VS_SARVAM" },
                { label: "OpenAI", value: describe(PRIVACY, status.openai), set: "VS_EXTERNAL" },
              ]} />
              <p className="mt-3 text-sm text-ink-soft">
                Even when a service is on, each case still needs your consent before anything from it is sent. See <Link href="/help#privacy">Help, Privacy</Link>.
              </p>
            </Block>

            <Block id="data" title="Data folder">
              <Rows rows={[{ label: "Folder", value: status.data_dir ? <code>{status.data_dir}</code> : "Not reported by the server.", set: "VS_DATA_DIR" }]} />
              <p className="mt-3 text-sm text-ink-soft">Case files, their history and exported drafts are kept in this folder on the server&apos;s machine.</p>
            </Block>
          </>
        ) : null}
      </div>
    </div>
  );
}
