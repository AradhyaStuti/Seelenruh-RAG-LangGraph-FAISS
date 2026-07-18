import { SoftAlert, SoftSiren, SoftFlame, SoftPhone, GentleShield } from "@/components/icons";

const contacts = [
  { label: "Police", number: "100", icon: SoftSiren },
  { label: "Ambulance", number: "102", icon: SoftPhone },
  { label: "Women Helpline", number: "1091", icon: GentleShield },
  { label: "iCall", number: "9152987821", icon: SoftPhone },
  { label: "Tele-MANAS", number: "14416", icon: SoftPhone },
  { label: "CHILDLINE", number: "1098", icon: GentleShield },
];

export default function EmergencyContacts() {
  return (
    <div className="mb-4 rounded-3xl border border-destructive/30 bg-destructive/5 p-4 sm:p-5 animate-pop-in petal-shadow">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-2xl bg-destructive/15 text-destructive flex items-center justify-center shrink-0">
          <SoftAlert className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <p className="font-headline text-base font-semibold text-destructive">
            Emergency detected
          </p>
          <p className="text-sm text-foreground/80 mt-0.5 leading-relaxed">
            If you are in immediate danger, contact emergency services right away.
          </p>
        </div>
      </div>

      <div className="mt-3.5 grid grid-cols-2 sm:grid-cols-3 gap-2">
        {contacts.map(({ label, number, icon: Icon }) => (
          <a
            key={label}
            href={`tel:${number}`}
            className="group flex items-center gap-2 rounded-2xl border border-destructive/25 bg-card/60 px-3 py-2.5 text-sm font-medium text-foreground/85 hover:bg-destructive/15 hover:border-destructive/45 hover:-translate-y-0.5 transition-all"
          >
            <span className="h-8 w-8 rounded-xl bg-destructive/10 text-destructive flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
              <Icon className="h-4 w-4" />
            </span>
            <span className="flex flex-col leading-tight min-w-0">
              <span className="truncate text-xs text-muted-foreground">{label}</span>
              <span className="font-semibold tabular-nums">{number}</span>
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}
