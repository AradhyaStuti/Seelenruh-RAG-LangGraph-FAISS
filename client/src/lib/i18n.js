// Lightweight i18n for the eligibility checker + document-templates UI chrome.
// Only the form labels and button text are translated. The legal document
// bodies themselves stay in English because they are statute-specific and
// would need lawyer review to translate accurately.
//
// Resolution rule: "auto" falls through to the browser language; everything
// else is the user's explicit pick from the LangToggle.

import { getLang, subscribeLang } from "@/lib/lang";
import { useEffect, useState } from "react";

const STRINGS = {
  en: {
    // shared
    cancel: "Cancel",
    close: "Close",
    back: "Back",
    download: "Download .txt",
    copy: "Copy",
    copied: "Copied",
    required: "required",

    // eligibility checker
    elig_title: "Scheme eligibility checker",
    elig_intro:
      "Tell us a little about your situation and we'll list the central + state schemes you're likely eligible for. This is a starting point, not a final answer — verify on each scheme's official portal.",
    elig_state: "State",
    elig_state_placeholder: "— Select —",
    elig_age: "Age",
    elig_age_placeholder: "e.g. 28",
    elig_income: "Annual income (₹)",
    elig_income_placeholder: "e.g. 200000",
    elig_gender: "Gender",
    elig_gender_female: "Female",
    elig_gender_male: "Male",
    elig_gender_other: "Other / prefer not to say",
    elig_student: "Student",
    elig_farmer: "Farmer",
    elig_check: "Check matches",
    elig_checking: "Checking…",
    elig_try_again: "Try different inputs",
    elig_no_matches:
      "No matches with these details. Try removing the income filter, or check the Aarogya chat for state-specific schemes.",
    elig_matches: (n) => `${n} likely ${n === 1 ? "match" : "matches"}`,
    elig_why: "Why:",
    elig_official: "Official portal →",
    elig_central: "central",
    elig_state_level: "state",

    // doc templates
    doc_title: "Legal document templates",
    doc_intro:
      "Fill the fields and we'll generate a ready-to-send draft. Templates are reviewed boilerplate — they're a starting point, not a substitute for a lawyer when the stakes are high.",
    doc_kind: "Document",
    doc_generate: "Generate draft",
    doc_drafting: "Drafting…",
    doc_edit: "Edit fields",
    doc_before_you_send: "Before you send",
    doc_t_rti: "RTI application",
    doc_t_rti_blurb: "Section 6 application under the Right to Information Act, 2005.",
    doc_t_cc: "Consumer complaint",
    doc_t_cc_blurb: "Complaint under Section 35 of the Consumer Protection Act, 2019.",
    doc_t_rent: "Rent / quit notice",
    doc_t_rent_blurb: "Notice under Section 106 of the Transfer of Property Act, 1882.",
  },
  hi: {
    cancel: "रद्द करें",
    close: "बंद करें",
    back: "वापस",
    download: ".txt डाउनलोड",
    copy: "कॉपी",
    copied: "कॉपी हुआ",
    required: "अनिवार्य",

    elig_title: "योजना पात्रता जाँचक",
    elig_intro:
      "अपनी जानकारी दें और हम आपके लिए संभावित केंद्र + राज्य योजनाएँ दिखाएँगे। यह एक शुरुआत है — हर योजना की आधिकारिक वेबसाइट पर पुष्टि ज़रूर करें।",
    elig_state: "राज्य",
    elig_state_placeholder: "— चुनें —",
    elig_age: "उम्र",
    elig_age_placeholder: "उदा. 28",
    elig_income: "वार्षिक आय (₹)",
    elig_income_placeholder: "उदा. 200000",
    elig_gender: "लिंग",
    elig_gender_female: "महिला",
    elig_gender_male: "पुरुष",
    elig_gender_other: "अन्य / नहीं बताना चाहते",
    elig_student: "छात्र / छात्रा",
    elig_farmer: "किसान",
    elig_check: "योजनाएँ देखें",
    elig_checking: "देखा जा रहा है…",
    elig_try_again: "अलग जानकारी आज़माएँ",
    elig_no_matches:
      "इन विवरणों से कोई योजना नहीं मिली। आय फ़िल्टर हटाकर देखें, या राज्य-विशेष योजनाओं के लिए Aarogya चैट से पूछें।",
    elig_matches: (n) => `${n} संभावित योजना${n === 1 ? "" : "एँ"}`,
    elig_why: "क्यों:",
    elig_official: "आधिकारिक पोर्टल →",
    elig_central: "केंद्र",
    elig_state_level: "राज्य",

    doc_title: "क़ानूनी दस्तावेज़ टेम्पलेट",
    doc_intro:
      "फ़ील्ड भरें और हम आपके लिए भेजने योग्य ड्राफ़्ट तैयार करेंगे। ये टेम्पलेट समीक्षित बॉयलरप्लेट हैं — शुरुआत के लिए ठीक, गंभीर मामलों में वकील का विकल्प नहीं।",
    doc_kind: "दस्तावेज़",
    doc_generate: "ड्राफ़्ट बनाएँ",
    doc_drafting: "तैयार किया जा रहा है…",
    doc_edit: "फ़ील्ड बदलें",
    doc_before_you_send: "भेजने से पहले",
    doc_t_rti: "RTI आवेदन",
    doc_t_rti_blurb: "सूचना का अधिकार अधिनियम 2005 की धारा 6 के तहत आवेदन।",
    doc_t_cc: "उपभोक्ता शिकायत",
    doc_t_cc_blurb: "उपभोक्ता संरक्षण अधिनियम 2019 की धारा 35 के तहत शिकायत।",
    doc_t_rent: "किराया / खाली करने का नोटिस",
    doc_t_rent_blurb: "संपत्ति अंतरण अधिनियम 1882 की धारा 106 के तहत नोटिस।",
  },
  de: {
    cancel: "Abbrechen",
    close: "Schließen",
    back: "Zurück",
    download: ".txt herunterladen",
    copy: "Kopieren",
    copied: "Kopiert",
    required: "erforderlich",

    elig_title: "Anspruchsprüfung für Programme",
    elig_intro:
      "Geben Sie ein paar Angaben zu Ihrer Situation an, und wir zeigen die zentralen und bundesstaatlichen Programme, für die Sie wahrscheinlich infrage kommen. Dies ist ein Ausgangspunkt — die offiziellen Portale haben das letzte Wort.",
    elig_state: "Bundesstaat",
    elig_state_placeholder: "— Auswählen —",
    elig_age: "Alter",
    elig_age_placeholder: "z. B. 28",
    elig_income: "Jahreseinkommen (₹)",
    elig_income_placeholder: "z. B. 200000",
    elig_gender: "Geschlecht",
    elig_gender_female: "Weiblich",
    elig_gender_male: "Männlich",
    elig_gender_other: "Andere / keine Angabe",
    elig_student: "Studierend",
    elig_farmer: "Landwirt:in",
    elig_check: "Treffer prüfen",
    elig_checking: "Wird geprüft…",
    elig_try_again: "Andere Angaben versuchen",
    elig_no_matches:
      "Mit diesen Angaben keine Treffer. Einkommensfilter entfernen oder im Aarogya-Chat nach bundesstaatlichen Programmen fragen.",
    elig_matches: (n) => `${n} mögliche${n === 1 ? "r Treffer" : " Treffer"}`,
    elig_why: "Grund:",
    elig_official: "Offizielles Portal →",
    elig_central: "zentral",
    elig_state_level: "bundesstaatlich",

    doc_title: "Vorlagen für juristische Dokumente",
    doc_intro:
      "Felder ausfüllen und wir erzeugen einen versandfertigen Entwurf. Die Vorlagen sind geprüfte Bausteine — ein Ausgangspunkt, kein Ersatz für eine Anwält:in, wenn etwas auf dem Spiel steht.",
    doc_kind: "Dokument",
    doc_generate: "Entwurf erstellen",
    doc_drafting: "Wird erstellt…",
    doc_edit: "Felder bearbeiten",
    doc_before_you_send: "Vor dem Versenden",
    doc_t_rti: "RTI-Antrag",
    doc_t_rti_blurb: "Antrag nach Section 6 des Right to Information Act, 2005.",
    doc_t_cc: "Verbraucherbeschwerde",
    doc_t_cc_blurb: "Beschwerde nach Section 35 des Consumer Protection Act, 2019.",
    doc_t_rent: "Kündigungsschreiben",
    doc_t_rent_blurb: "Kündigung nach Section 106 des Transfer of Property Act, 1882.",
  },
};

function resolveLang(picked) {
  if (picked && picked !== "auto" && STRINGS[picked]) return picked;
  if (typeof navigator !== "undefined") {
    const nav = (navigator.language || "").toLowerCase();
    if (nav.startsWith("hi")) return "hi";
    if (nav.startsWith("de")) return "de";
  }
  return "en";
}

export function t(key, ...args) {
  const lang = resolveLang(getLang());
  const dict = STRINGS[lang] || STRINGS.en;
  const value = dict[key] ?? STRINGS.en[key];
  if (typeof value === "function") return value(...args);
  return value ?? key;
}

// Hook so components re-render when the user changes language.
export function useT() {
  const [, force] = useState(0);
  useEffect(() => subscribeLang(() => force((n) => n + 1)), []);
  return t;
}
