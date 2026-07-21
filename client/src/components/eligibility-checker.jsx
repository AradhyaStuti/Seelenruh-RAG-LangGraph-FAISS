// Aarogya's scheme eligibility checker. Form-driven, no LLM — the rules
// live in `server/schemes.py` and the user can read them.

import { useState } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { matchSchemes } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useT } from "@/lib/i18n";

const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
  "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
  "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
  "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
  "Uttarakhand", "West Bengal",
];

const initialForm = {
  state: "",
  age: "",
  incomeAnnual: "",
  gender: "",
  casteCategory: "",
  residenceType: "",
  landholding: "",
  isStudent: false,
  isFarmer: false,
  isDisabled: false,
  isWidow: false,
};

export function EligibilityChecker({ open, onOpenChange }) {
  const [form, setForm] = useState(initialForm);
  const [busy, setBusy] = useState(false);
  const [matches, setMatches] = useState(null);
  const { toast } = useToast();
  const t = useT();

  const reset = () => {
    setForm(initialForm);
    setMatches(null);
  };

  const handleClose = (next) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const handleCheck = async (e) => {
    e?.preventDefault?.();
    setBusy(true);
    try {
      const payload = {
        state: form.state || undefined,
        age: form.age ? Number(form.age) : undefined,
        incomeAnnual: form.incomeAnnual ? Number(form.incomeAnnual) : undefined,
        gender: form.gender || undefined,
        casteCategory: form.casteCategory || undefined,
        residenceType: form.residenceType || undefined,
        landholding: form.landholding ? Number(form.landholding) : undefined,
        isStudent: form.isStudent,
        isFarmer: form.isFarmer,
        isDisabled: form.isDisabled,
        isWidow: form.isWidow,
      };
      const result = await matchSchemes(payload);
      setMatches(result.matches || []);
    } catch (err) {
      toast({
        title: "Couldn't check eligibility",
        description: err?.message || "Try again in a moment.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={handleClose}>
      <AlertDialogContent className="w-[calc(100vw-1.5rem)] max-w-lg gap-3 rounded-2xl border-primary/15 bg-card p-5 sm:p-6 max-h-[92vh] overflow-y-auto">
        <AlertDialogTitle className="font-headline text-base sm:text-lg">
          {t("elig_title")}
        </AlertDialogTitle>
        <AlertDialogDescription className="text-[13px] leading-relaxed text-muted-foreground sm:text-sm">
          {t("elig_intro")}
        </AlertDialogDescription>

        {matches === null ? (
          <form onSubmit={handleCheck} className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="el-state" className="text-xs">{t("elig_state")}</Label>
                <select
                  id="el-state"
                  value={form.state}
                  onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">{t("elig_state_placeholder")}</option>
                  {INDIAN_STATES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="el-age" className="text-xs">{t("elig_age")}</Label>
                <Input
                  id="el-age"
                  type="number"
                  min="0"
                  max="120"
                  placeholder={t("elig_age_placeholder")}
                  value={form.age}
                  onChange={(e) => setForm((f) => ({ ...f, age: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="el-income" className="text-xs">{t("elig_income")}</Label>
                <Input
                  id="el-income"
                  type="number"
                  min="0"
                  placeholder={t("elig_income_placeholder")}
                  value={form.incomeAnnual}
                  onChange={(e) => setForm((f) => ({ ...f, incomeAnnual: e.target.value }))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="el-gender" className="text-xs">{t("elig_gender")}</Label>
                <select
                  id="el-gender"
                  value={form.gender}
                  onChange={(e) => setForm((f) => ({ ...f, gender: e.target.value }))}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">Any / prefer not to say</option>
                  <option value="female">{t("elig_gender_female")}</option>
                  <option value="male">{t("elig_gender_male")}</option>
                  <option value="other">{t("elig_gender_other")}</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="el-caste" className="text-xs">Caste Category</Label>
                <select
                  id="el-caste"
                  value={form.casteCategory}
                  onChange={(e) => setForm((f) => ({ ...f, casteCategory: e.target.value }))}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">Prefer not to say / General</option>
                  <option value="sc">SC (Scheduled Caste)</option>
                  <option value="st">ST (Scheduled Tribe)</option>
                  <option value="obc">OBC</option>
                  <option value="general">General</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="el-residence" className="text-xs">Area of Residence</Label>
                <select
                  id="el-residence"
                  value={form.residenceType}
                  onChange={(e) => setForm((f) => ({ ...f, residenceType: e.target.value }))}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">Not specified</option>
                  <option value="rural">Rural (village / gram panchayat)</option>
                  <option value="urban">Urban (town / city)</option>
                </select>
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="el-land" className="text-xs">Land Owned (acres) — for farmers</Label>
                <Input
                  id="el-land"
                  type="number"
                  min="0"
                  step="0.1"
                  placeholder="e.g. 2.5 (leave blank if unknown)"
                  value={form.landholding}
                  onChange={(e) => setForm((f) => ({ ...f, landholding: e.target.value }))}
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-3 pt-1">
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-input/60 bg-background/60 px-3 py-2 text-sm hover:bg-accent/30">
                <input
                  type="checkbox"
                  checked={form.isStudent}
                  onChange={(e) => setForm((f) => ({ ...f, isStudent: e.target.checked }))}
                  className="h-4 w-4 accent-primary"
                />
                {t("elig_student")}
              </label>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-input/60 bg-background/60 px-3 py-2 text-sm hover:bg-accent/30">
                <input
                  type="checkbox"
                  checked={form.isFarmer}
                  onChange={(e) => setForm((f) => ({ ...f, isFarmer: e.target.checked }))}
                  className="h-4 w-4 accent-primary"
                />
                {t("elig_farmer")}
              </label>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-input/60 bg-background/60 px-3 py-2 text-sm hover:bg-accent/30">
                <input
                  type="checkbox"
                  checked={form.isDisabled}
                  onChange={(e) => setForm((f) => ({ ...f, isDisabled: e.target.checked }))}
                  className="h-4 w-4 accent-primary"
                />
                Person with Disability
              </label>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-input/60 bg-background/60 px-3 py-2 text-sm hover:bg-accent/30">
                <input
                  type="checkbox"
                  checked={form.isWidow}
                  onChange={(e) => setForm((f) => ({ ...f, isWidow: e.target.checked }))}
                  className="h-4 w-4 accent-primary"
                />
                Widow
              </label>
            </div>

            <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleClose(false)}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {t("cancel")}
              </Button>
              <Button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {busy ? t("elig_checking") : t("elig_check")}
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-2">
            {matches.length === 0 ? (
              <div className="rounded-xl border border-border/40 bg-background/40 px-3 py-4 text-sm text-muted-foreground">
                {t("elig_no_matches")}
              </div>
            ) : (
              <>
                <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  {t("elig_matches", matches.length)}
                </div>
                <ul className="space-y-2">
                  {matches.map((m) => (
                    <li
                      key={m.id}
                      className="rounded-xl border border-border/40 bg-background/40 px-3 py-2.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-foreground/90">{m.name}</div>
                          <div className="mt-0.5 text-[12px] leading-snug text-muted-foreground">
                            {m.summary}
                          </div>
                        </div>
                        <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
                          {m.level === "central" ? t("elig_central") : t("elig_state_level")}
                        </span>
                      </div>
                      <div className="mt-1.5 text-[11px] italic text-muted-foreground/90">
                        {t("elig_why")} {m.reason}
                      </div>
                      <a
                        href={m.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 inline-flex text-[11px] font-medium text-primary hover:underline"
                      >
                        {t("elig_official")}
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}

            <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={reset}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {t("elig_try_again")}
              </Button>
              <Button
                type="button"
                onClick={() => handleClose(false)}
                className="h-11 w-full rounded-full sm:h-10 sm:w-auto"
              >
                {t("close")}
              </Button>
            </div>
          </div>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}
