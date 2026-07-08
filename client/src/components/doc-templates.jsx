// Umang's legal document templates. Pure form → server template render →
// copy / download. No LLM in the loop so users get reproducible documents.

import { useEffect, useMemo, useState } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { renderTemplate } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useT } from "@/lib/i18n";

const TEMPLATES = {
  rti: {
    label: "RTI application",
    blurb: "Section 6 application under the Right to Information Act, 2005.",
    fields: [
      { key: "applicantName", label: "Your name", required: true },
      { key: "applicantAddress", label: "Your address", required: true, textarea: true },
      { key: "applicantPhone", label: "Phone (optional)" },
      { key: "publicAuthority", label: "Public authority (department / ministry)", required: true },
      { key: "pioAddress", label: "PIO office address (optional)", textarea: true },
      { key: "informationSought", label: "Information sought (be specific)", required: true, textarea: true, rows: 4 },
      { key: "period", label: "Time period it relates to (optional)" },
      { key: "isBpl", label: "I am a BPL applicant (fee exempt)", checkbox: true },
    ],
  },
  consumer_complaint: {
    label: "Consumer complaint",
    blurb: "Complaint under Section 35 of the Consumer Protection Act, 2019.",
    fields: [
      { key: "complainantName", label: "Your name", required: true },
      { key: "complainantAddress", label: "Your address", required: true, textarea: true },
      { key: "complainantPhone", label: "Phone (optional)" },
      { key: "opposingParty", label: "Opposite party (seller / service provider)", required: true },
      { key: "opposingPartyAddress", label: "Opposite party's address", textarea: true },
      { key: "purchaseDate", label: "Date of purchase / service" },
      { key: "amountPaid", label: "Amount paid (₹)" },
      { key: "grievance", label: "What went wrong (defect / deficiency / unfair practice)", required: true, textarea: true, rows: 4 },
      { key: "reliefSought", label: "Relief you want (refund / replacement / compensation)" },
    ],
  },
  rent_notice: {
    label: "Rent / quit notice",
    blurb: "Notice under Section 106 of the Transfer of Property Act, 1882.",
    fields: [
      { key: "senderName", label: "Your name (landlord / advocate)", required: true },
      { key: "senderAddress", label: "Your address", required: true, textarea: true },
      { key: "tenantName", label: "Tenant's name", required: true },
      { key: "propertyAddress", label: "Premises address", required: true, textarea: true },
      { key: "monthlyRent", label: "Monthly rent (₹)" },
      { key: "rentDueAmount", label: "Total arrears (₹)" },
      { key: "monthsDue", label: "Months unpaid" },
      { key: "noticePeriodDays", label: "Notice period (days)", placeholder: "15" },
      { key: "reason", label: "Reason", placeholder: "non-payment of rent" },
    ],
  },
};

function emptyFor(kind) {
  return Object.fromEntries(
    (TEMPLATES[kind]?.fields || []).map((f) => [f.key, f.checkbox ? false : ""])
  );
}

export function DocTemplates({ open, onOpenChange }) {
  const [kind, setKind] = useState("rti");
  const [fields, setFields] = useState(() => emptyFor("rti"));
  const [busy, setBusy] = useState(false);
  const [rendered, setRendered] = useState(null);
  const [copied, setCopied] = useState(false);
  const { toast } = useToast();
  const t = useT();

  const def = TEMPLATES[kind];
  const kindLabel = {
    rti: t("doc_t_rti"),
    consumer_complaint: t("doc_t_cc"),
    rent_notice: t("doc_t_rent"),
  };
  const kindBlurb = {
    rti: t("doc_t_rti_blurb"),
    consumer_complaint: t("doc_t_cc_blurb"),
    rent_notice: t("doc_t_rent_blurb"),
  };

  useEffect(() => {
    if (open) {
      setFields(emptyFor(kind));
      setRendered(null);
      setCopied(false);
    }
  }, [open, kind]);

  const canSubmit = useMemo(
    () => def.fields.filter((f) => f.required).every((f) => fields[f.key]?.toString().trim()),
    [def, fields]
  );

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    if (!canSubmit) return;
    setBusy(true);
    try {
      const result = await renderTemplate({ kind, fields });
      setRendered(result);
    } catch (err) {
      toast({
        title: "Couldn't render template",
        description: err?.message || "Try again in a moment.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleCopy = async () => {
    if (!rendered?.body) return;
    try {
      await navigator.clipboard.writeText(rendered.body);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast({ title: "Copy blocked by browser", variant: "destructive" });
    }
  };

  const handleDownload = () => {
    if (!rendered?.body) return;
    const blob = new Blob([rendered.body], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${kind}-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="w-[calc(100vw-1.5rem)] max-w-2xl gap-3 rounded-2xl border-primary/15 bg-card p-5 sm:p-6 max-h-[92vh] overflow-y-auto">
        <AlertDialogTitle className="font-headline text-base sm:text-lg">
          {t("doc_title")}
        </AlertDialogTitle>
        <AlertDialogDescription className="text-[13px] leading-relaxed text-muted-foreground sm:text-sm">
          {t("doc_intro")}
        </AlertDialogDescription>

        <div className="space-y-1.5">
          <Label htmlFor="doc-kind" className="text-xs">{t("doc_kind")}</Label>
          <select
            id="doc-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {Object.keys(TEMPLATES).map((k) => (
              <option key={k} value={k}>{kindLabel[k]}</option>
            ))}
          </select>
          <p className="text-[11px] text-muted-foreground/90">{kindBlurb[kind]}</p>
        </div>

        {!rendered ? (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {def.fields.map((f) => (
                <div
                  key={f.key}
                  className={`space-y-1.5 ${f.textarea ? "sm:col-span-2" : ""}`}
                >
                  {f.checkbox ? (
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-input/60 bg-background/60 px-3 py-2 text-sm hover:bg-accent/30">
                      <input
                        type="checkbox"
                        checked={!!fields[f.key]}
                        onChange={(e) =>
                          setFields((p) => ({ ...p, [f.key]: e.target.checked }))
                        }
                        className="h-4 w-4 accent-primary"
                      />
                      {f.label}
                    </label>
                  ) : (
                    <>
                      <Label htmlFor={`doc-${f.key}`} className="text-xs">
                        {f.label}
                        {f.required && (
                          <span className="ml-0.5 text-destructive" title={t("required")}>*</span>
                        )}
                      </Label>
                      {f.textarea ? (
                        <textarea
                          id={`doc-${f.key}`}
                          rows={f.rows || 2}
                          value={fields[f.key] || ""}
                          onChange={(e) =>
                            setFields((p) => ({ ...p, [f.key]: e.target.value }))
                          }
                          placeholder={f.placeholder}
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        />
                      ) : (
                        <Input
                          id={`doc-${f.key}`}
                          value={fields[f.key] || ""}
                          onChange={(e) =>
                            setFields((p) => ({ ...p, [f.key]: e.target.value }))
                          }
                          placeholder={f.placeholder}
                        />
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>

            <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {t("cancel")}
              </Button>
              <Button
                type="submit"
                disabled={!canSubmit || busy}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {busy ? t("doc_drafting") : t("doc_generate")}
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-3">
            <div className="text-sm font-medium text-foreground/90">{rendered.title}</div>
            <pre className="max-h-[40vh] overflow-auto rounded-xl border border-border/40 bg-background/60 p-3 text-[12px] leading-relaxed text-foreground/85 whitespace-pre-wrap font-mono">
              {rendered.body}
            </pre>
            {rendered.notes?.length > 0 && (
              <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-[12px] text-amber-900/90 dark:text-amber-100/90">
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide">{t("doc_before_you_send")}</div>
                <ul className="space-y-1 leading-snug">
                  {rendered.notes.map((n, i) => (
                    <li key={i}>• {n}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-between">
              <Button
                type="button"
                variant="outline"
                onClick={() => setRendered(null)}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {t("doc_edit")}
              </Button>
              <div className="flex flex-col-reverse gap-2 sm:flex-row">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCopy}
                  className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
                >
                  {copied ? t("copied") : t("copy")}
                </Button>
                <Button
                  type="button"
                  onClick={handleDownload}
                  className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
                >
                  {t("download")}
                </Button>
              </div>
            </div>
          </div>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}
