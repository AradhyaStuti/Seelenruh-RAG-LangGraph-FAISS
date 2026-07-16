// LegalTimeline — visual step-by-step legal process timeline for Umang responses
import { useState } from "react";
import { cn } from "@/lib/utils";

const TIMELINES = {
  salary: {
    title: "Salary Recovery — Legal Process",
    acts: ["Payment of Wages Act 1936", "Industrial Disputes Act 1947"],
    steps: [
      {
        title: "Send a Legal Notice",
        duration: "Day 1–7",
        cost: "₹500–₹2,000",
        docs: ["Appointment letter", "Pay slips", "Bank statements"],
        note: "Give employer 15 days to pay. Keep a copy of the notice.",
      },
      {
        title: "File Complaint with Labour Commissioner",
        duration: "Day 8–30",
        cost: "Free",
        docs: ["Legal notice copy", "Employment proof", "Unpaid salary details"],
        note: "Labour Commissioner can summon employer and order payment within 60 days.",
      },
      {
        title: "Labour Court Application",
        duration: "1–3 months",
        cost: "₹200–₹1,000",
        docs: ["LC complaint copy", "All earlier docs", "Witness details if any"],
        note: "File under Section 33C(2) of the Industrial Disputes Act for dues calculation.",
      },
      {
        title: "Court Order & Recovery",
        duration: "3–12 months",
        cost: "Nil (recovered from employer)",
        docs: ["Decree copy"],
        note: "Court can order salary recovery + 7.5% interest per annum on arrears.",
      },
    ],
  },

  eviction: {
    title: "Tenancy Dispute / Eviction — Legal Process",
    acts: ["Transfer of Property Act 1882", "State Rent Control Acts", "CPC Order 21"],
    steps: [
      {
        title: "Issue Eviction / Rent Notice",
        duration: "Day 1",
        cost: "₹200–₹500",
        docs: ["Rent agreement", "Evidence of default or misuse"],
        note: "Send by registered post. Minimum 15-day notice for non-payment; 30 days for other grounds.",
      },
      {
        title: "File Rent Controller / Civil Court Petition",
        duration: "Week 2–4",
        cost: "₹500–₹2,000",
        docs: ["Notice copy", "Rent receipts", "Rent agreement", "Property documents"],
        note: "Many states have dedicated Rent Control Courts with faster timelines.",
      },
      {
        title: "Hearing & Evidence",
        duration: "3–18 months",
        cost: "₹2,000–₹10,000",
        docs: ["Same as above + witness affidavits"],
        note: "Mediation is often offered at this stage. Consider accepting if terms are fair.",
      },
      {
        title: "Court Order",
        duration: "On disposal",
        cost: "Nil",
        docs: ["Decree copy"],
        note: "Court may order eviction, back-rent + 6% interest. Possession handed by court bailiff.",
      },
    ],
  },

  consumer: {
    title: "Consumer Complaint — Legal Process",
    acts: ["Consumer Protection Act 2019"],
    steps: [
      {
        title: "Send Demand Notice to Seller / Service Provider",
        duration: "Day 1–7",
        cost: "₹100–₹500",
        docs: ["Invoice / receipt", "Photos of defective product / poor service", "Warranty card"],
        note: "Give the company 15–30 days to resolve. Many companies settle at this stage.",
      },
      {
        title: "File Complaint on INGRAM / e-Daakhil",
        duration: "Day 8–15",
        cost: "Free (online portal)",
        docs: ["Demand notice copy", "Invoice", "Evidence of defect"],
        note: "Lodge at consumerhelpline.gov.in or e-daakhil.nic.in. Keep complaint number.",
      },
      {
        title: "District Consumer Commission",
        duration: "1–5 months",
        cost: "₹200–₹2,000 (based on claim amount)",
        docs: ["Complaint form", "All evidence", "Affidavit"],
        note: "For claims up to ₹50 lakh. Commission aims to decide within 150 days.",
      },
      {
        title: "Award & Compensation",
        duration: "On order",
        cost: "Nil",
        docs: ["Order copy"],
        note: "Entitled to replacement / refund + compensation for mental agony + litigation costs.",
      },
    ],
  },

  domestic_violence: {
    title: "Domestic Violence — Legal Process (PWDVA 2005)",
    acts: ["Protection of Women from Domestic Violence Act 2005", "IPC Section 498A"],
    steps: [
      {
        title: "Contact Protection Officer / Police",
        duration: "Immediate",
        cost: "Free",
        docs: ["Any available evidence (photos, messages, medical reports)"],
        note: "Protection Officer is appointed by every district. Police must register DV report. Emergency helpline: 181 (Women Helpline) / 100.",
      },
      {
        title: "File DV Complaint in Magistrate Court",
        duration: "Day 1–7",
        cost: "Free",
        docs: ["Domestic Incident Report (DIR)", "ID proof", "Medical records", "Witness details"],
        note: "Magistrate can pass interim Protection Order on the same day if required.",
      },
      {
        title: "Interim Orders (Protection, Residence, Maintenance)",
        duration: "1–4 weeks",
        cost: "Free",
        docs: ["Petition filed by Protection Officer"],
        note: "Respondent can be barred from entering the shared household immediately.",
      },
      {
        title: "Final Hearing & Order",
        duration: "3–12 months",
        cost: "Free (state provides advocate if needed)",
        docs: ["All evidence", "Witness statements"],
        note: "Court can award monetary relief, child custody, and residence rights.",
      },
    ],
  },

  fir: {
    title: "FIR & Criminal Complaint — Process",
    acts: ["Bharatiya Nagarik Suraksha Sanhita 2023 (BNSS)", "IPC / BNS"],
    steps: [
      {
        title: "Approach the Jurisdictional Police Station",
        duration: "Day 1",
        cost: "Free",
        docs: ["Written complaint", "ID proof", "Any evidence"],
        note: "Police must register FIR for cognizable offences. Get FIR copy free of charge.",
      },
      {
        title: "If Police Refuses — File Section 156(3) CrPC Application",
        duration: "Day 2–10",
        cost: "₹500–₹2,000",
        docs: ["Written complaint copy", "Proof of refusal"],
        note: "Magistrate can direct police to register FIR. Alternatively file private complaint under Section 200 CrPC.",
      },
      {
        title: "Police Investigation",
        duration: "60–90 days",
        cost: "Free",
        docs: ["Cooperate with investigation; provide evidence"],
        note: "Police must file chargesheet within 60 days (90 days if accused is in custody).",
      },
      {
        title: "Trial in Criminal Court",
        duration: "6 months – several years",
        cost: "₹5,000–₹50,000 (if private counsel)",
        docs: ["All evidence", "Witness list"],
        note: "NALSA provides free legal aid — apply at your nearest District Legal Services Authority.",
      },
    ],
  },

  rti: {
    title: "RTI (Right to Information) — Process",
    acts: ["Right to Information Act 2005"],
    steps: [
      {
        title: "Draft RTI Application",
        duration: "Day 1",
        cost: "₹10 (application fee)",
        docs: ["Written application in Hindi or English", "ID proof"],
        note: "Send to the Public Information Officer (PIO) of the relevant government department.",
      },
      {
        title: "PIO Responds",
        duration: "30 days",
        cost: "₹2 per page (additional copies)",
        docs: [],
        note: "If life/liberty is involved, information must be provided within 48 hours.",
      },
      {
        title: "First Appeal (if unsatisfied)",
        duration: "30–45 days",
        cost: "Free",
        docs: ["Original application", "PIO response or non-response"],
        note: "Appeal to the First Appellate Authority (senior officer in the same department).",
      },
      {
        title: "Second Appeal to Central / State Information Commission",
        duration: "60–90 days",
        cost: "Free",
        docs: ["All previous correspondence"],
        note: "Information Commission can impose penalty of ₹250/day (max ₹25,000) on defaulting PIO.",
      },
    ],
  },
};

const PATTERNS = [
  { key: "salary",            re: /\b(salary|wage|dues|arrears?|unpaid\s+pay|payment\s+of\s+wages|labour\s+commissioner|section\s+33c)\b/i },
  { key: "eviction",         re: /\b(evict|eviction|tenant|landlord|rent\s+control|vacate\s+premises|notice\s+to\s+quit)\b/i },
  { key: "consumer",         re: /\b(consumer\s+(complaint|forum|commission|court)|defective\s+(product|goods)|consumer\s+protection|e-daakhil|ingram|refund)\b/i },
  { key: "domestic_violence", re: /\b(domestic\s+violence|pwdva|protection\s+order|protection\s+of\s+women|dv\s+case|498a)\b/i },
  { key: "fir",              re: /\b(fir|first\s+information\s+report|cognizable\s+offence|156\(3\)|magistrate\s+complaint|chargesheet)\b/i },
  { key: "rti",              re: /\b(rti|right\s+to\s+information|public\s+information\s+officer|pio|information\s+commission)\b/i },
];

export function detectTimelineKey(text) {
  for (const { key, re } of PATTERNS) {
    if (re.test(text)) return key;
  }
  return null;
}

export function LegalTimeline({ messageContent }) {
  const [open, setOpen] = useState(false);

  const key = detectTimelineKey(messageContent || "");
  if (!key) return null;

  const timeline = TIMELINES[key];

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[10px] text-primary/70 hover:text-primary transition-colors font-medium"
        aria-expanded={open}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
          <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
        View legal timeline &amp; steps
        <svg
          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden
          className={cn("transition-transform", open && "rotate-180")}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="mt-2 rounded-2xl border border-primary/20 bg-primary/5 p-4 space-y-4">
          <div>
            <h4 className="text-[12px] font-semibold text-primary/90">{timeline.title}</h4>
            <div className="mt-1 flex flex-wrap gap-1">
              {timeline.acts.map((act) => (
                <span
                  key={act}
                  className="rounded-full px-2 py-0.5 bg-primary/10 text-primary text-[10px] border border-primary/20"
                >
                  {act}
                </span>
              ))}
            </div>
          </div>

          {/* Steps */}
          <ol className="relative border-l border-primary/30 space-y-4 ml-1">
            {timeline.steps.map((step, idx) => (
              <li key={idx} className="pl-5 relative">
                {/* Dot on timeline */}
                <span className="absolute -left-[7px] top-[3px] h-3.5 w-3.5 rounded-full border-2 border-primary/50 bg-background flex items-center justify-center">
                  <span className="text-[8px] font-bold text-primary/80">{idx + 1}</span>
                </span>

                <div className="space-y-1">
                  <p className="text-[11px] font-semibold text-foreground/90">{step.title}</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                      </svg>
                      {step.duration}
                    </span>
                    <span className="flex items-center gap-1">
                      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                      </svg>
                      {step.cost}
                    </span>
                  </div>
                  {step.docs.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {step.docs.map((doc) => (
                        <span
                          key={doc}
                          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 bg-card/80 border border-border/40 text-[9px] text-muted-foreground"
                        >
                          <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                          </svg>
                          {doc}
                        </span>
                      ))}
                    </div>
                  )}
                  {step.note && (
                    <p className="text-[10px] text-muted-foreground/70 italic leading-relaxed">{step.note}</p>
                  )}
                </div>
              </li>
            ))}
          </ol>

          <p className="text-[9px] text-muted-foreground/50 italic">
            Timelines are approximate and vary by jurisdiction. Always verify with a qualified lawyer or NALSA (nalsa.gov.in).
          </p>
        </div>
      )}
    </div>
  );
}
