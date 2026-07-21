import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { SettingsResponse } from "../lib/types";

interface SettingsPanelProps {
  project: string;
  onClose: () => void;
  onSaved: (provider: string) => void;
}

type FormState = {
  provider: string;
  ollamaHost: string;
  ollamaModel: string;
  lmstudioHost: string;
  lmstudioModel: string;
  openrouterHost: string;
  openrouterModel: string;
  openrouterApiKey: string;
  openrouterKeySet: boolean;
};

const EMPTY: FormState = {
  provider: "ollama",
  ollamaHost: "",
  ollamaModel: "",
  lmstudioHost: "",
  lmstudioModel: "",
  openrouterHost: "",
  openrouterModel: "",
  openrouterApiKey: "",
  openrouterKeySet: false,
};

function fromResponse(r: SettingsResponse): FormState {
  return {
    provider: r.gateway.provider,
    ollamaHost: r.ollama.host ?? "",
    ollamaModel: r.ollama.model ?? "",
    lmstudioHost: r.lmstudio.host ?? "",
    lmstudioModel: r.lmstudio.model ?? "",
    openrouterHost: r.openrouter.host ?? "",
    openrouterModel: r.openrouter.model ?? "",
    openrouterApiKey: "",
    openrouterKeySet: r.openrouter.api_key_set ?? false,
  };
}

type ProviderKey = "ollama" | "lmstudio" | "openrouter";

interface ProviderModels {
  models: string[];
  loading: boolean;
  error: string | null;
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-2xs font-medium text-ink-muted">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:border-blue focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
      />
    </label>
  );
}

function ModelSelect({
  value,
  onChange,
  models,
  loading,
  error,
  onFetch,
  onTest,
  host,
  disabled = false,
}: {
  value: string;
  onChange: (v: string) => void;
  models: string[];
  loading: boolean;
  error: string | null;
  onFetch: () => void;
  onTest: () => void;
  host: string;
  disabled?: boolean;
}) {
  const hasModels = models.length > 0;

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onFetch}
          disabled={loading || !host.trim() || disabled}
          className="rounded-md border border-border bg-bg-subtle px-3 py-1.5 text-xs text-ink hover:bg-bg-inset disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Fetching..." : "Fetch Models"}
        </button>
        <button
          type="button"
          onClick={onTest}
          disabled={loading || !host.trim() || (!hasModels && !value.trim()) || disabled}
          className="rounded-md border border-border bg-bg-subtle px-3 py-1.5 text-xs text-ink hover:bg-bg-inset disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Test
        </button>
      </div>
      {hasModels ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || loading}
          className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-sm text-ink focus:border-blue focus:outline-none disabled:opacity-50"
        >
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={loading ? "Fetching models…" : hasModels ? "Select a model" : "Enter model name manually (fetch to populate)"}
          className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-faint"
        />
      )}
      {error && <p className="text-2xs text-red">{error}</p>}
      {hasModels && !loading && (
        <p className="text-2xs text-ink-faint">{models.length} model{models.length !== 1 ? "s" : ""} available</p>
      )}
    </div>
  );
}

function ProviderCard({
  title,
  active,
  children,
}: {
  title: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-lg border p-3.5 ${active ? "border-blue bg-blue-dim/30" : "border-border bg-bg-subtle"}`}
    >
      <div className="mb-2.5 flex items-center gap-2">
        <h3 className="text-sm font-medium text-ink">{title}</h3>
        {active && (
          <span className="rounded bg-blue px-1.5 py-0.5 text-2xs font-medium text-white">active</span>
        )}
      </div>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}

export default function SettingsPanel({ project, onClose, onSaved }: SettingsPanelProps) {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ollamaModels, setOllamaModels] = useState<ProviderModels>({ models: [], loading: false, error: null });
  const [lmstudioModels, setLmstudioModels] = useState<ProviderModels>({ models: [], loading: false, error: null });
  const [openrouterModels, setOpenrouterModels] = useState<ProviderModels>({ models: [], loading: false, error: null });

  useEffect(() => {
    let cancelled = false;
    api
      .getSettings(project)
      .then((r) => { if (!cancelled) setForm(fromResponse(r)); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [project]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const fetchModels = async (provider: ProviderKey) => {
    const host = form[`${provider}Host` as keyof FormState] as string;
    const apiKey = provider === "openrouter" ? (form.openrouterApiKey || undefined) : undefined;

    const setter = provider === "ollama" ? setOllamaModels
      : provider === "lmstudio" ? setLmstudioModels
      : setOpenrouterModels;

    setter({ models: [], loading: true, error: null });

    try {
      const resp = await api.fetchModels(provider, host, apiKey);
      setter({ models: resp.models, loading: false, error: resp.error ?? null });
    } catch (e) {
      setter({ models: [], loading: false, error: String(e) });
    }
  };

  const testProvider = async (provider: ProviderKey) => {
    const host = form[`${provider}Host` as keyof FormState] as string;
    const model = form[`${provider}Model` as keyof FormState] as string;
    const apiKey = provider === "openrouter" ? (form.openrouterApiKey || undefined) : undefined;

    const setter = provider === "ollama" ? setOllamaModels
      : provider === "lmstudio" ? setLmstudioModels
      : setOpenrouterModels;

    const currentModels = (provider === "ollama" ? ollamaModels
      : provider === "lmstudio" ? lmstudioModels
      : openrouterModels).models;

    setter({ models: currentModels, loading: true, error: null });

    try {
      const resp = await api.testProvider(provider, host, model || undefined, apiKey);
      setter({ models: currentModels, loading: false, error: resp.ok ? null : resp.error ?? "Test failed" });
      if (!resp.ok) {
        setError(`${provider} test failed: ${resp.error}`);
      } else {
        setError(null);
      }
    } catch (e) {
      setter({ models: currentModels, loading: false, error: String(e) });
      setError(`${provider} test error: ${e}`);
    }
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateSettings(project, {
        provider: form.provider,
        ollama: { host: form.ollamaHost, model: form.ollamaModel },
        lmstudio: { host: form.lmstudioHost, model: form.lmstudioModel },
        openrouter: {
          host: form.openrouterHost,
          model: form.openrouterModel,
          ...(form.openrouterApiKey ? { api_key: form.openrouterApiKey } : {}),
        },
      });
      setForm(fromResponse(updated));
      onSaved(updated.gateway.provider);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const anyLoading = ollamaModels.loading || lmstudioModels.loading || openrouterModels.loading;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px]">
      <div className="max-h-[85vh] w-[38rem] overflow-y-auto rounded-xl border border-border bg-bg p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Provider & model settings</h2>
          <button onClick={onClose} className="text-ink-faint hover:text-ink">✕</button>
        </div>

        {loading ? (
          <p className="text-sm text-ink-muted">Loading…</p>
        ) : (
          <>
            <label className="mb-4 block">
              <span className="mb-1 block text-2xs font-medium text-ink-muted">
                Active provider (used by every task in this project)
              </span>
              <select
                value={form.provider}
                onChange={(e) => set("provider", e.target.value)}
                className="w-full rounded-md border border-border bg-bg px-2.5 py-1.5 text-sm text-ink"
              >
                <option value="ollama">Ollama (local)</option>
                <option value="lmstudio">LM Studio (local)</option>
                <option value="openrouter">OpenRouter (hosted)</option>
              </select>
            </label>

            <div className="space-y-3">
              <ProviderCard title="Ollama" active={form.provider === "ollama"}>
                <Field label="Host" value={form.ollamaHost} onChange={(v) => set("ollamaHost", v)} placeholder="http://localhost:11434" />
                <ModelSelect
                  value={form.ollamaModel}
                  onChange={(v) => set("ollamaModel", v)}
                  models={ollamaModels.models}
                  loading={ollamaModels.loading}
                  error={ollamaModels.error}
                  onFetch={() => fetchModels("ollama")}
                  onTest={() => testProvider("ollama")}
                  host={form.ollamaHost}
                  disabled={form.provider !== "ollama"}
                />
              </ProviderCard>

              <ProviderCard title="LM Studio" active={form.provider === "lmstudio"}>
                <Field label="Host" value={form.lmstudioHost} onChange={(v) => set("lmstudioHost", v)} placeholder="http://localhost:1234/v1" />
                <ModelSelect
                  value={form.lmstudioModel}
                  onChange={(v) => set("lmstudioModel", v)}
                  models={lmstudioModels.models}
                  loading={lmstudioModels.loading}
                  error={lmstudioModels.error}
                  onFetch={() => fetchModels("lmstudio")}
                  onTest={() => testProvider("lmstudio")}
                  host={form.lmstudioHost}
                  disabled={form.provider !== "lmstudio"}
                />
              </ProviderCard>

              <ProviderCard title="OpenRouter" active={form.provider === "openrouter"}>
                <Field label="Host" value={form.openrouterHost} onChange={(v) => set("openrouterHost", v)} placeholder="https://openrouter.ai/api/v1" />
                <ModelSelect
                  value={form.openrouterModel}
                  onChange={(v) => set("openrouterModel", v)}
                  models={openrouterModels.models}
                  loading={openrouterModels.loading}
                  error={openrouterModels.error}
                  onFetch={() => fetchModels("openrouter")}
                  onTest={() => testProvider("openrouter")}
                  host={form.openrouterHost}
                  disabled={form.provider !== "openrouter"}
                />
                <Field
                  label={form.openrouterKeySet ? "API key (saved -- leave blank to keep it)" : "API key"}
                  value={form.openrouterApiKey}
                  onChange={(v) => set("openrouterApiKey", v)}
                  placeholder={form.openrouterKeySet ? "•••••••••••••••• (unchanged)" : "sk-or-..."}
                  type="password"
                />
              </ProviderCard>
            </div>

            {error && <p className="mt-3 text-xs text-red">{error}</p>}

            <div className="mt-5 flex justify-end gap-2">
              <button onClick={onClose} className="rounded-md px-3 py-1.5 text-sm text-ink-muted hover:bg-bg-inset">
                Cancel
              </button>
              <button
                onClick={save}
                disabled={saving || anyLoading}
                className="rounded-md bg-blue px-3.5 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}