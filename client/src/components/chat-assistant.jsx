import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import ReactMarkdown from "react-markdown";
import {
  PetalHeart,
  FeatherScale,
  SunBloom,
  GentleShield,
  SoftSend,
  SoftCopy,
  SoftCheck,
  SoftRefresh,
  SoftUser,
  BlossomLogo,
  HeartBookmark,
  SoftAlert,
  SoftMic,
  SoftStop,
  SoftSpeaker,
} from "@/components/icons";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Form, FormControl, FormField, FormItem } from "@/components/ui/form";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import EmergencyContacts from "@/components/emergency-contacts";
import { QuickReplies } from "@/components/quick-replies";
import { MoodCheckIn } from "@/components/mood-checkin";
import { ChatHistoryDrawer } from "@/components/chat-history";
import { loadMoments, saveMoment, removeMoment } from "@/components/saved-moments";
import { RoutingTrace } from "@/components/routing-trace";
import { SafetySteps } from "@/components/safety-steps";
import { streamUserMessage, buildHistory, summarizeConversation, fetchAllSummaries, submitFeedbackToServer, parseDocument } from "@/lib/api";
import { EligibilityChecker } from "@/components/eligibility-checker";
import { loadAll, saveAll, newSession, titleFromMessages } from "@/lib/sessions";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { useVoice } from "@/hooks/use-voice";
import { getLang, setLang, subscribeLang, LANGS } from "@/lib/lang";
import { speak, cancelSpeech, isSpeaking, primeVoices } from "@/lib/speech";

const formSchema = z.object({
  message: z
    .string()
    .min(1, { message: "Message cannot be empty." })
    .max(4000, { message: "Message is too long." }),
});

const ACTIVE_DOMAIN_KEY = "seelenruh:active-domain:v1";

const domainConfig = {
  "Mental Health": {
    icon: PetalHeart,
    persona: "Usha",
    subtitle: "A quiet, judgement-free space to talk through what's on your mind.",
    disclaimer: "Not a substitute for professional mental health care. If you're in crisis, please contact iCall (+91 9152987821) or Tele-MANAS (14416).",
    initialMessage:
      "Hi, I'm Usha. I'm here to listen — what's on your mind today?",
    quickReplies: [
      "I'm feeling anxious lately",
      "Tips for better sleep",
      "How do I find a therapist?",
      "Aaj mood theek nahi hai",
    ],
  },
  Legal: {
    icon: FeatherScale,
    persona: "Umang",
    subtitle: "Plain-language answers cited from real laws and official sources.",
    disclaimer: "General legal information only — not legal advice. For your situation, consult a lawyer or contact NALSA (nalsa.gov.in) for free legal aid.",
    initialMessage:
      "Hi, I'm Umang. Tell me what's happening and I'll explain your rights in plain words.",
    quickReplies: [
      "How do I file an FIR?",
      "Tenant rights in India",
      "Consumer Protection Act basics",
      "RTI filing process",
    ],
  },
  "Government Schemes": {
    icon: SunBloom,
    persona: "Aarogya",
    subtitle: "Find the schemes, benefits and entitlements that apply to you.",
    initialMessage:
      "Hi, I'm Aarogya. Tell me a bit about yourself and I'll suggest schemes you may be eligible for.",
    quickReplies: [
      "Ayushman Bharat eligibility",
      "PM Kisan Yojana details",
      "Scholarship for SC/ST students",
      "How to apply for ration card",
    ],
  },
  Safety: {
    icon: GentleShield,
    persona: "Raksha",
    subtitle: "Calm, step-by-step guidance for emergencies and personal safety.",
    initialMessage:
      "Hi, I'm Raksha. Tell me what's happening and we'll work through it step by step.",
    quickReplies: [
      "Women's safety helplines",
      "What to do during a fire",
      "Cybercrime reporting steps",
      "Emergency: I need help",
    ],
  },
};

const formatTime = (ts) => {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
};

const moodHints = {
  joyful: "(user is feeling joyful) ",
  calm: "(user is feeling calm) ",
  tired: "(user is feeling tired) ",
  anxious: "(user is anxious) ",
  sad: "(user is sad) ",
};

// Client-side emergency pre-check — triggers before the API classify call so
// EmergencyContacts appear instantly instead of after the 2-4s LLM round-trip.
// False positives are acceptable: we just pre-show contacts; the LLM still
// classifies and the session isEmergency flag is set by the API response.
const EMERGENCY_RE =
  /\b(suicid(?:e|al)|kill(?:ing)?\s+my(?:self)?|end\s+my\s+life|want\s+to\s+die|don'?t\s+want\s+to\s+live|hurt(?:ing)?\s+my(?:self)?|self[- ]?harm|cutting\s+my(?:self)?|overdose|he'?s?\s+hitting\s+me|she'?s?\s+hitting\s+me|being\s+beaten|domestic\s+violence|being\s+abused|being\s+raped?|sexual\s+assault|heart\s+attack|can'?t\s+breathe|i\s+(?:am\s+)?dying|need\s+help\s+now|in\s+(?:immediate\s+)?danger|not\s+safe(?:\s+right\s+now)?|mujhe\s+maara|maar\s+diya|maar\s+raha|khatam\s+karna\s+chahta|bachao)\b/i;

function looksLikeEmergency(text) {
  return EMERGENCY_RE.test(text);
}

const welcomeMessageFor = (domain) => ({
  id: `welcome-${domain}`,
  role: "assistant",
  content: domainConfig[domain].initialMessage,
  timestamp: Date.now(),
});

export default function ChatAssistant({ onDomainChange }) {
  const [selectedDomain, setSelectedDomain] = useState("Mental Health");
  const [domainSessions, setDomainSessions] = useState(() => loadAll());
  const [loadingByDomain, setLoadingByDomain] = useState({});
  const [hydrated, setHydrated] = useState(false);

  const [pendingDomain, setPendingDomain] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [savedIds, setSavedIds] = useState(new Set());
  const [mood, setMood] = useState(null);
  const [eligOpen, setEligOpen] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [feedbackMap, setFeedbackMap] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("seelenruh:feedback:v1") || "{}");
    } catch { return {}; }
  });
  // Pre-emptive emergency flag set by client-side keyword scan before API responds
  const [preEmergency, setPreEmergency] = useState(false);
  // Document context attached for the next message
  const [attachedContext, setAttachedContext] = useState(null); // { name, text }
  // ID of the assistant message currently being streamed (null when not streaming)
  const [streamingMsgId, setStreamingMsgId] = useState(null);
  // ID of the assistant message whose TTS is playing (null = silent)
  const [speakingId, setSpeakingId] = useState(null);
  // Language preference — drives STT lang, Whisper lang, LLM lang, TTS lang
  const [lang, setLangState] = useState(() => getLang());

  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const { toast } = useToast();

  // Keep lang in sync across tabs / components
  useEffect(() => {
    const unsub = subscribeLang((code) => setLangState(code));
    return unsub;
  }, []);

  // Prime browser TTS voices on mount (Chrome loads them async)
  useEffect(() => {
    primeVoices();
    return () => cancelSpeech();
  }, []);

  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: { message: "" },
  });

  // Ref to the latest sendTextMessage — set after sendTextMessage is declared below.
  // useVoice's onResultRef always calls the latest onVoiceResult which closes over
  // this ref, so voice recognition always dispatches with up-to-date component state.
  const sendTextRef = useRef(null);

  // Voice input hook — uses Web Speech API (primary) or Whisper fallback.
  // onResult is NOT memoized — useVoice stores it in onResultRef each render,
  // so it always calls the latest version with fresh state (no stale closure).
  const { isListening, interimTranscript, start: startListening, stop: stopListening, supported: voiceSupported } = useVoice({
    lang,
    onResult: (text) => {
      if (!text?.trim()) return;
      console.log("[chat] voice onResult received:", JSON.stringify(text));
      cancelSpeech();
      setSpeakingId(null);
      form.setValue("message", text);
      // Call via ref so we always get the sendTextMessage with current domain/session state.
      if (sendTextRef.current) {
        console.log("[chat] calling sendTextMessage from voice");
        sendTextRef.current(text);
      } else {
        console.error("[chat] sendTextRef.current is null — voice result dropped!");
      }
    },
    onError: (msg) => {
      toast({ title: "Voice input error", description: msg, variant: "destructive" });
    },
  });

  // Hydrate persisted state on mount
  useEffect(() => {
    setDomainSessions(loadAll());
    try {
      const lastDomain = window.localStorage.getItem(ACTIVE_DOMAIN_KEY);
      if (lastDomain && domainConfig[lastDomain]) {
        setSelectedDomain(lastDomain);
        onDomainChange(lastDomain);
      }
      const seeded = new Set();
      loadMoments().forEach((m) => seeded.add(m.content));
      setSavedIds(seeded);
    } catch (err) {
      console.warn("Failed to restore state", err);
    } finally {
      setHydrated(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cross-device summary hydrate: pull every server-stored summary for this
  // user and overlay it onto the local sessions. Lets a user pick up where
  // they left off on another device. Best-effort — fails silently if the
  // server is down or the user is signed out.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetchAllSummaries();
      if (cancelled || !res?.summaries?.length) return;
      setDomainSessions((prev) => {
        const next = { ...prev };
        for (const row of res.summaries) {
          const ds = next[row.persona];
          if (!ds) continue;
          const found = ds.sessions.find((s) => s.id === row.sessionId);
          if (!found) continue;
          if ((found.summary || "") === row.summary) continue;
          next[row.persona] = {
            ...ds,
            sessions: ds.sessions.map((s) =>
              s.id === row.sessionId
                ? { ...s, summary: row.summary, summarizedAt: Date.parse(row.updatedAt || "") || Date.now() }
                : s
            ),
          };
        }
        return next;
      });
    })();
    return () => { cancelled = true; };
  }, []);

  // Persist sessions + active domain
  useEffect(() => {
    if (!hydrated) return;
    saveAll(domainSessions);
    try {
      window.localStorage.setItem(ACTIVE_DOMAIN_KEY, selectedDomain);
    } catch {
      // ignore
    }
  }, [domainSessions, selectedDomain, hydrated]);

  const currentDomainState = domainSessions[selectedDomain];
  const activeSession = useMemo(
    () => currentDomainState.sessions.find((s) => s.id === currentDomainState.activeId) || null,
    [currentDomainState]
  );
  const welcomeMessage = useMemo(() => welcomeMessageFor(selectedDomain), [selectedDomain]);
  const visibleMessages = activeSession ? activeSession.messages : [welcomeMessage];
  const isLoading = !!loadingByDomain[selectedDomain];
  const isEmergency = !!activeSession?.isEmergency;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visibleMessages, isLoading]);

  const setDomainLoading = (loading) =>
    setLoadingByDomain((prev) => ({ ...prev, [selectedDomain]: loading }));

  const ensureActiveSession = (initialMessages) => {
    let id = currentDomainState.activeId;
    if (id) return id;
    const fresh = newSession(initialMessages);
    id = fresh.id;
    setDomainSessions((prev) => ({
      ...prev,
      [selectedDomain]: {
        sessions: [fresh, ...prev[selectedDomain].sessions],
        activeId: id,
      },
    }));
    return id;
  };

  const updateActiveMessages = (updater, opts = {}) => {
    setDomainSessions((prev) => {
      const ds = prev[selectedDomain];
      if (!ds.activeId) return prev;
      const sessions = ds.sessions.map((s) => {
        if (s.id !== ds.activeId) return s;
        const nextMessages = updater(s.messages);
        return {
          ...s,
          messages: nextMessages,
          title: titleFromMessages(nextMessages),
          updatedAt: Date.now(),
          isEmergency: s.isEmergency || !!opts.markEmergency,
        };
      });
      return { ...prev, [selectedDomain]: { ...ds, sessions } };
    });
  };

  const startNewChat = () => {
    setDomainSessions((prev) => ({
      ...prev,
      [selectedDomain]: { ...prev[selectedDomain], activeId: null },
    }));
    setDomainLoading(false);
    setPreEmergency(false);
    inputRef.current?.focus();
  };

  const selectSession = (id) => {
    setDomainSessions((prev) => ({
      ...prev,
      [selectedDomain]: { ...prev[selectedDomain], activeId: id },
    }));
    setPreEmergency(false);
  };

  const deleteSession = (id) => {
    setDomainSessions((prev) => {
      const ds = prev[selectedDomain];
      const sessions = ds.sessions.filter((s) => s.id !== id);
      const activeId = ds.activeId === id ? null : ds.activeId;
      return { ...prev, [selectedDomain]: { sessions, activeId } };
    });
    toast({ title: "Chat deleted" });
  };

  const summariseSession = async ({ silent = false } = {}) => {
    if (!activeSession || summarizing) return;
    // Skip the auto-generated welcome greeting; only summarise real exchanges.
    const realMessages = (activeSession.messages || []).filter(
      (m) => !String(m.id || "").startsWith("welcome-")
    );
    if (realMessages.length < 2) {
      if (!silent) {
        toast({
          title: "Not enough to summarise yet",
          description: "Have a few more exchanges first.",
        });
      }
      return;
    }
    setSummarizing(true);
    try {
      const payload = realMessages.slice(-30).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      // Pass persona + sessionId so the server persists this summary
       // keyed on (user, persona, session). Other devices fetch it back.
      const result = await summarizeConversation(payload, {
        persona: selectedDomain,
        sessionId: activeSession.id,
      });
      if (!result.summary) throw new Error("Empty summary returned.");
      const userMessageCount = realMessages.filter((m) => m.role === "user").length;
      setDomainSessions((prev) => {
        const ds = prev[selectedDomain];
        const sessions = ds.sessions.map((s) =>
          s.id === activeSession.id
            ? {
                ...s,
                summary: result.summary,
                summarizedAt: Date.now(),
                summarizedAtUserMsg: userMessageCount,
              }
            : s
        );
        return { ...prev, [selectedDomain]: { ...ds, sessions } };
      });
      if (!silent) toast({ title: "Summary updated" });
    } catch (err) {
      if (!silent) {
        toast({
          title: "Couldn't summarise",
          description: err?.message || "Try again in a moment.",
          variant: "destructive",
        });
      }
    } finally {
      setSummarizing(false);
    }
  };

  // Background auto-summary: kicks in after every 2 user messages — self-evolving memory.
  // The server already maintains a rolling summary autonomously; this local summary
  // is a client-side backup visible in the conversation memory card.
  const AUTO_SUMMARY_EVERY = 2;
  useEffect(() => {
    if (!activeSession || isLoading || summarizing) return;
    const realMessages = (activeSession.messages || []).filter(
      (m) => !String(m.id || "").startsWith("welcome-")
    );
    const userMsgCount = realMessages.filter((m) => m.role === "user").length;
    const lastAt = activeSession.summarizedAtUserMsg || 0;
    const shouldRun =
      userMsgCount > 0 &&
      userMsgCount >= AUTO_SUMMARY_EVERY &&
      userMsgCount - lastAt >= AUTO_SUMMARY_EVERY;
    if (shouldRun) {
      summariseSession({ silent: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSession?.messages.length, isLoading]);

  const handleDomainSwitch = useCallback(
    (newDomain) => {
      setSelectedDomain(newDomain);
      onDomainChange(newDomain);
      setPendingDomain(null);
      setPreEmergency(false);
    },
    [onDomainChange]
  );

  const handleTabChange = (value) => {
    if (value !== selectedDomain) {
      setPendingDomain(value);
    }
  };

  const copyMessage = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((v) => (v === id ? null : v)), 1500);
    } catch {
      toast({
        title: "Couldn't copy",
        description: "Clipboard access was denied.",
        variant: "destructive",
      });
    }
  };

  const toggleSave = (content) => {
    const next = new Set(savedIds);
    if (next.has(content)) {
      const target = loadMoments().find((m) => m.content === content);
      if (target) removeMoment(target.id);
      next.delete(content);
      toast({ title: "Removed" });
    } else {
      saveMoment({
        content,
        persona: domainConfig[selectedDomain].persona,
        domain: selectedDomain,
      });
      next.add(content);
      toast({ title: "Saved" });
    }
    setSavedIds(next);
  };

  const submitFeedback = (messageId, vote) => {
    setFeedbackMap((prev) => {
      const next = { ...prev };
      // Toggle off if clicking the same button
      if (next[messageId] === vote) {
        delete next[messageId];
        // Remove from server too (send "remove" is not supported, but a re-vote
        // with opposite polarity won't happen here — just clear locally)
      } else {
        next[messageId] = vote;
        // Fire-and-forget to server; localStorage is the primary store
        submitFeedbackToServer(messageId, vote, selectedDomain);
      }
      try { localStorage.setItem("seelenruh:feedback:v1", JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const exportChat = () => {
    const persona = domainConfig[selectedDomain].persona;
    const msgs = visibleMessages.filter((m) => !m.id?.startsWith("welcome-"));
    if (!msgs.length) {
      toast({ title: "Nothing to export", description: "Start a conversation first." });
      return;
    }
    const lines = [
      `Seelenruh — ${persona} conversation`,
      `Exported: ${new Date().toLocaleString()}`,
      `Domain: ${selectedDomain}`,
      "─".repeat(50),
      "",
      ...msgs.map((m) => {
        const who = m.role === "user" ? "You" : persona;
        const time = formatTime(m.timestamp);
        return `[${who}${time ? " · " + time : ""}]\n${m.content}\n`;
      }),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `seelenruh-${persona.toLowerCase()}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast({ title: "Conversation exported" });
  };

  // plain text read locally; PDF + DOCX sent to server for extraction
  const PLAIN_TEXT_EXTS = new Set([".txt", ".md", ".csv", ".json", ".log"]);
  const SERVER_EXTS = new Set([".pdf", ".docx"]);
  const MAX_LOCAL_BYTES = 300_000;

  const handleFileAttach = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    const ext = ("." + file.name.split(".").pop()).toLowerCase();

    if (SERVER_EXTS.has(ext)) {
      // PDF / DOCX — send to server for extraction
      if (file.size > 5 * 1024 * 1024) {
        toast({ title: "File too large", description: "Max 5 MB for PDF/Word files.", variant: "destructive" });
        return;
      }
      try {
        toast({ title: "Extracting text…", description: `Reading ${file.name}` });
        const result = await parseDocument(file);
        setAttachedContext({ name: result.name, text: result.text });
        toast({
          title: "File attached",
          description: `${result.name} (${result.chars.toLocaleString()} chars${result.truncated ? ", truncated" : ""}) will be included in your next message.`,
        });
      } catch (err) {
        toast({ title: "Couldn't read file", description: err?.message || "Extraction failed.", variant: "destructive" });
      }
      return;
    }

    if (!PLAIN_TEXT_EXTS.has(ext)) {
      toast({
        title: "Unsupported file type",
        description: "Supported: .txt, .md, .csv, .json, .pdf, .docx",
        variant: "destructive",
      });
      return;
    }

    // Plain text — read locally
    if (file.size > MAX_LOCAL_BYTES) {
      toast({ title: "File too large", description: "Please attach a file under 300 KB.", variant: "destructive" });
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const raw = (ev.target?.result || "").toString();
      const text = raw.slice(0, 3000) + (raw.length > 3000 ? "\n[...truncated]" : "");
      setAttachedContext({ name: file.name, text });
      toast({ title: "File attached", description: `${file.name} will be included in your next message.` });
    };
    reader.onerror = () => {
      toast({ title: "Couldn't read file", description: "Only plain text files are supported.", variant: "destructive" });
    };
    reader.readAsText(file);
  };

  const composeQuery = (text) => (mood ? moodHints[mood] + text : text);

  const sendTextMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    // Stop any ongoing TTS and voice input when user sends
    cancelSpeech();
    setSpeakingId(null);
    if (isListening) stopListening();

    // If a file is attached, prepend it as context for this message then clear it
    const ctx = attachedContext;
    const queryWithCtx = ctx
      ? `[Attached file: ${ctx.name}]\n${ctx.text}\n\n${trimmed}`
      : trimmed;
    if (ctx) setAttachedContext(null);

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,   // display only the user's text, not the raw context blob
      timestamp: Date.now(),
      hasAttachment: !!ctx,
      attachmentName: ctx?.name,
    };

    // Client-side emergency pre-check: show EmergencyContacts immediately,
    // before the LLM classify node returns (saves 2-4s in a real crisis).
    if (looksLikeEmergency(trimmed)) {
      setPreEmergency(true);
    }

    // Create session on first message if needed
    const isFresh = !currentDomainState.activeId;
    if (isFresh) {
      ensureActiveSession([userMessage]);
    } else {
      updateActiveMessages((msgs) => [...msgs, userMessage]);
    }

    setDomainLoading(true);
    form.reset();

    // Build history from the messages we just committed
    const historySnapshot = isFresh
      ? [userMessage]
      : [...(activeSession?.messages || []), userMessage];

    // Add a streaming placeholder message so tokens appear progressively
    const streamMsgId = crypto.randomUUID();
    updateActiveMessages((msgs) => [
      ...msgs,
      { id: streamMsgId, role: "assistant", content: "", timestamp: Date.now(), streaming: true },
    ]);
    setStreamingMsgId(streamMsgId);

    try {
      const result = await streamUserMessage(
        {
          query: composeQuery(queryWithCtx),
          domain: selectedDomain,
          history: buildHistory(historySnapshot),
          lang,
        },
        {
          onToken: (token) => {
            setDomainSessions((prev) => {
              const ds = prev[selectedDomain];
              if (!ds.activeId) return prev;
              return {
                ...prev,
                [selectedDomain]: {
                  ...ds,
                  sessions: ds.sessions.map((s) =>
                    s.id !== ds.activeId
                      ? s
                      : {
                          ...s,
                          messages: s.messages.map((m) =>
                            m.id === streamMsgId ? { ...m, content: m.content + token } : m
                          ),
                        }
                  ),
                },
              };
            });
          },
        }
      );

      if (result.error) throw new Error(result.error);

      // Finalize the streaming message — fill in metadata and clear streaming flag
      setDomainSessions((prev) => {
        const ds = prev[selectedDomain];
        if (!ds.activeId) return prev;
        const sessions = ds.sessions.map((s) => {
          if (s.id !== ds.activeId) return s;
          const nextMessages = s.messages.map((m) =>
            m.id !== streamMsgId
              ? m
              : {
                  ...m,
                  streaming: false,
                  // Use server's authoritative text; fall back to accumulated tokens
                  content: result.response || m.content,
                  sources: result.sources || [],
                  citedIndices: result.citedIndices || [],
                  confidence: result.confidence || "None",
                  routing: result.routing || null,
                  goal: result.goal || null,
                  webSearched: !!result.webSearched,
                }
          );
          return {
            ...s,
            messages: nextMessages,
            title: titleFromMessages(nextMessages),
            updatedAt: Date.now(),
            isEmergency: s.isEmergency || !!result.isEmergency,
          };
        });
        return { ...prev, [selectedDomain]: { ...ds, sessions } };
      });

      // Auto-play TTS for the completed assistant response
      if (result.response?.trim()) {
        const ttsText = result.response.trim();
        setSpeakingId(streamMsgId);
        speak(ttsText, {
          lang,
          domain: selectedDomain,
          onEnd: () => setSpeakingId(null),
          onPlayBlocked: () => setSpeakingId(null),
        });
      }
    } catch (error) {
      // Replace placeholder with error message
      setDomainSessions((prev) => {
        const ds = prev[selectedDomain];
        if (!ds.activeId) return prev;
        return {
          ...prev,
          [selectedDomain]: {
            ...ds,
            sessions: ds.sessions.map((s) =>
              s.id !== ds.activeId
                ? s
                : {
                    ...s,
                    messages: s.messages.map((m) =>
                      m.id === streamMsgId
                        ? { ...m, streaming: false, content: "Sorry, something went wrong. Please try again." }
                        : m
                    ),
                  }
            ),
          },
        };
      });
      toast({
        title: "Error",
        description: error?.message || "Please try again.",
        variant: "destructive",
      });
    } finally {
      setStreamingMsgId(null);
      setDomainLoading(false);
    }
  };

  // Update ref every render — gives onVoiceResult the latest sendTextMessage
  // with current selectedDomain, activeSession, lang, etc. (no stale closure).
  sendTextRef.current = sendTextMessage;

  const onSubmit = (values) => sendTextMessage(values.message);

  const inputValue = form.watch("message");
  const remaining = useMemo(() => 4000 - (inputValue?.length ?? 0), [inputValue]);
  const messageCount = visibleMessages.length;
  const currentPersona = domainConfig[selectedDomain];
  const sessionCount = currentDomainState.sessions.length;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-4">
        <MoodCheckIn onMoodChange={setMood} />

        <Card className="w-full rounded-[2rem] glass-strong petal-shadow transition-all duration-500 overflow-hidden border-border/40">
          <CardHeader className="text-center pb-3 pt-6">
            <CardTitle className="font-headline text-2xl sm:text-[1.75rem] font-bold tracking-tight">
              Talk to <span className="text-gradient">{currentPersona.persona}</span>
            </CardTitle>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1 max-w-sm mx-auto leading-relaxed">
              {currentPersona.subtitle}
            </p>
            {currentPersona.disclaimer && (
              <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-1.5 max-w-sm mx-auto leading-snug opacity-80">
                ⚠ {currentPersona.disclaimer}
              </p>
            )}
          </CardHeader>

          <CardContent className="pt-0 px-3 sm:px-5 pb-5">
            <Tabs value={selectedDomain} onValueChange={handleTabChange} className="w-full">
              <TabsList className="grid w-full grid-cols-2 sm:grid-cols-4 h-auto bg-transparent p-0 gap-2">
                {Object.entries(domainConfig).map(([name, { icon: Icon, persona }]) => (
                  <TabsTrigger
                    key={name}
                    value={name}
                    className={cn(
                      "group relative py-3 rounded-2xl border border-border/45 bg-card/55 backdrop-blur transition-all duration-300",
                      "data-[state=active]:bg-gradient-to-br data-[state=active]:from-primary data-[state=active]:to-primary/80",
                      "data-[state=active]:text-primary-foreground data-[state=active]:shadow-lg data-[state=active]:border-primary/40 data-[state=active]:scale-[1.02]",
                      "hover:-translate-y-0.5 hover:bg-card/85 hover:border-primary/50",
                      "focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    )}
                  >
                    <Icon className="mr-2 h-5 w-5 transition-transform duration-300 group-hover:scale-110 group-data-[state=active]:rotate-[-6deg]" />
                    <span className="font-medium text-[13px] sm:text-sm">{persona}</span>
                  </TabsTrigger>
                ))}
              </TabsList>

              <div className="mt-4 p-3 sm:p-4 rounded-[1.75rem] bg-background/55 border border-border/50 shadow-inner backdrop-blur-sm">
                <div className="mb-3 flex items-center justify-between gap-1 px-1 flex-wrap">
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500">
                      <span className="absolute inset-0 rounded-full bg-emerald-500 animate-ping opacity-60" />
                    </span>
                    <span>{currentPersona.persona} online</span>
                    <span className="opacity-50">·</span>
                    <span className="hidden sm:inline tabular-nums">
                      {messageCount} {messageCount === 1 ? "message" : "messages"}
                    </span>
                    {/* Active goal badge — shows when the agent has detected a multi-turn goal */}
                    {(() => {
                      const lastGoal = [...visibleMessages].reverse().find((m) => m.goal)?.goal;
                      if (!lastGoal) return null;
                      return (
                        <span
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
                          style={{
                            background: "hsl(var(--primary) / 0.12)",
                            color: "hsl(var(--primary))",
                            border: "1px solid hsl(var(--primary) / 0.25)",
                          }}
                          title={`Current goal: ${lastGoal}`}
                        >
                          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" />
                          </svg>
                          {lastGoal.length > 30 ? lastGoal.slice(0, 30) + "…" : lastGoal}
                        </span>
                      );
                    })()}
                  </div>
                  <div className="flex items-center gap-1 flex-wrap justify-end">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setHistoryOpen(true)}
                          className="text-[11px] gap-1.5 h-8 rounded-full hover:bg-primary/10 hover:text-primary"
                        >
                          <BlossomLogo className="h-3.5 w-3.5" />
                          <span className="hidden sm:inline">History</span>
                          {sessionCount > 0 && (
                            <span className="ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary/20 px-1 text-[10px] font-semibold text-primary">
                              {sessionCount}
                            </span>
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Past chats with {currentPersona.persona}</TooltipContent>
                    </Tooltip>
                    {selectedDomain === "Government Schemes" && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setEligOpen(true)}
                            className="text-[11px] gap-1.5 h-8 rounded-full hover:bg-primary/10 hover:text-primary"
                          >
                            <SunBloom className="h-3.5 w-3.5" />
                            <span className="hidden sm:inline">Eligibility</span>
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Check which schemes you may qualify for</TooltipContent>
                      </Tooltip>
                    )}
                    {messageCount >= 4 && activeSession && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={summariseSession}
                            disabled={summarizing}
                            className="text-[11px] gap-1.5 h-8 rounded-full hover:bg-primary/10 hover:text-primary"
                          >
                            <PetalHeart className="h-3.5 w-3.5" />
                            <span className="hidden sm:inline">{summarizing ? "Summarising…" : activeSession.summary ? "Refresh summary" : "Summarise"}</span>
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>One-paragraph recap of this conversation</TooltipContent>
                      </Tooltip>
                    )}
                    {activeSession && visibleMessages.length > 1 && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={exportChat}
                            className="text-[11px] gap-1.5 h-8 rounded-full hover:bg-primary/10 hover:text-primary"
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                              <polyline points="7 10 12 15 17 10" />
                              <line x1="12" y1="15" x2="12" y2="3" />
                            </svg>
                            <span className="hidden sm:inline">Export</span>
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Download conversation as text file</TooltipContent>
                      </Tooltip>
                    )}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={startNewChat}
                          disabled={isLoading || !currentDomainState.activeId}
                          className="text-[11px] gap-1.5 h-8 rounded-full hover:bg-primary/10 hover:text-primary"
                        >
                          <SoftRefresh className="h-3.5 w-3.5" />
                          <span className="hidden sm:inline">New chat</span>
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Start a fresh conversation</TooltipContent>
                    </Tooltip>
                  </div>
                </div>

                <ScrollArea className="h-[52vh] sm:h-[58vh] pr-2">
                  <div className="space-y-5">
                    {activeSession?.summary && (
                      <div className="rounded-2xl border border-primary/20 bg-primary/5 px-3.5 py-2.5 text-[12px] leading-relaxed">
                        <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-primary/85">
                          <PetalHeart className="h-3 w-3" />
                          Conversation memory
                        </div>
                        <p className="text-foreground/85">{activeSession.summary}</p>
                      </div>
                    )}
                    {(isEmergency || preEmergency) && <EmergencyContacts />}
                    {visibleMessages.map((message) => {
                      const saved = savedIds.has(message.content);
                      return (
                        <div
                          key={message.id}
                          className={cn(
                            "flex items-end gap-3",
                            message.role === "user"
                              ? "justify-end animate-slide-in-right"
                              : "justify-start animate-slide-in-left"
                          )}
                        >
                          {message.role === "assistant" && (
                            <Avatar className="h-9 w-9 ring-2 ring-primary/30 shrink-0">
                              <AvatarFallback className="bg-gradient-to-br from-primary/90 to-accent text-primary-foreground">
                                <BlossomLogo className="h-5 w-5" />
                              </AvatarFallback>
                            </Avatar>
                          )}
                          <div className="flex flex-col max-w-[85%] sm:max-w-md">
                            <div
                              className={cn(
                                "relative rounded-2xl p-3.5 text-sm prose prose-sm prose-p:m-0 transition-all duration-300",
                                "prose-a:text-primary hover:prose-a:text-primary/80 prose-a:underline-offset-2",
                                "prose-strong:text-foreground/90",
                                "group hover:shadow-md",
                                message.role === "user"
                                  ? "bg-gradient-to-br from-primary/85 to-primary text-primary-foreground rounded-br-md petal-shadow"
                                  : "bg-card/95 text-card-foreground rounded-bl-md border border-border/40 petal-shadow"
                              )}
                            >
                              <div className="min-w-0 break-words">
                                {message.role === "user" && message.hasAttachment && (
                                  <p className="mb-1 flex items-center gap-1 text-[10px] text-primary-foreground/70">
                                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                                      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                                    </svg>
                                    {message.attachmentName}
                                  </p>
                                )}
                                {message.role === "assistant" ? (
                                  <>
                                    {message.routing?.routedDomain === "Safety" && (
                                      <SafetySteps text={message.content} />
                                    )}
                                    <ReactMarkdown
                                      components={{
                                        a: ({ node: _node, ...props }) => (
                                          <a {...props} target="_blank" rel="noopener noreferrer" />
                                        ),
                                      }}
                                    >
                                      {message.content}
                                    </ReactMarkdown>
                                    {message.streaming && (
                                      <span
                                        className="inline-block w-[2px] h-[1em] bg-current align-middle ml-0.5 opacity-80"
                                        style={{ animation: "pulse 0.9s ease-in-out infinite" }}
                                        aria-hidden
                                      />
                                    )}
                                  </>
                                ) : (
                                  <p className="whitespace-pre-wrap">{message.content}</p>
                                )}
                              </div>

                              {message.role === "user" && (
                                <div className="mt-2 -mb-1 flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 rounded-full text-primary-foreground/80 hover:text-primary-foreground hover:bg-primary-foreground/10"
                                        onClick={() => copyMessage(message.id, message.content)}
                                      >
                                        {copiedId === message.id ? (
                                          <SoftCheck className="h-3.5 w-3.5" />
                                        ) : (
                                          <SoftCopy className="h-3.5 w-3.5" />
                                        )}
                                        <span className="sr-only">Copy</span>
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                      {copiedId === message.id ? "Copied" : "Copy"}
                                    </TooltipContent>
                                  </Tooltip>
                                </div>
                              )}

                              {message.role === "assistant" && (
                                <div className="mt-2 -mb-1 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                  {/* TTS play/stop button */}
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        className={cn("h-7 w-7 rounded-full", speakingId === message.id && "text-primary")}
                                        onClick={() => {
                                          if (speakingId === message.id && isSpeaking()) {
                                            cancelSpeech();
                                            setSpeakingId(null);
                                          } else {
                                            cancelSpeech();
                                            setSpeakingId(message.id);
                                            speak(message.content, {
                                              lang,
                                              domain: selectedDomain,
                                              onEnd: () => setSpeakingId(null),
                                              onPlayBlocked: () => setSpeakingId(null),
                                            });
                                          }
                                        }}
                                      >
                                        <SoftSpeaker className={cn("h-3.5 w-3.5 transition-all", speakingId === message.id && "scale-110")} />
                                        <span className="sr-only">{speakingId === message.id ? "Stop" : "Listen"}</span>
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>{speakingId === message.id ? "Stop" : "Listen"}</TooltipContent>
                                  </Tooltip>
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 rounded-full"
                                        onClick={() => copyMessage(message.id, message.content)}
                                      >
                                        {copiedId === message.id ? (
                                          <SoftCheck className="h-3.5 w-3.5 text-emerald-600" />
                                        ) : (
                                          <SoftCopy className="h-3.5 w-3.5" />
                                        )}
                                        <span className="sr-only">Copy</span>
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                      {copiedId === message.id ? "Copied" : "Copy"}
                                    </TooltipContent>
                                  </Tooltip>
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        className={cn(
                                          "h-7 w-7 rounded-full",
                                          saved && "text-primary opacity-100"
                                        )}
                                        onClick={() => toggleSave(message.content)}
                                      >
                                        <HeartBookmark
                                          className={cn("h-3.5 w-3.5 transition-all", saved && "scale-110")}
                                        />
                                        <span className="sr-only">{saved ? "Unsave" : "Save"}</span>
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>{saved ? "Saved" : "Save"}</TooltipContent>
                                  </Tooltip>

                                  {/* Feedback */}
                                  {!message.id?.startsWith("welcome-") && (
                                    <>
                                      <div className="w-px h-4 bg-border/50 mx-0.5" />
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            variant="ghost"
                                            size="icon"
                                            className={cn(
                                              "h-7 w-7 rounded-full transition-all",
                                              feedbackMap[message.id] === "up" && "text-emerald-600 opacity-100 bg-emerald-50"
                                            )}
                                            onClick={() => submitFeedback(message.id, "up")}
                                            aria-label="Helpful"
                                            aria-pressed={feedbackMap[message.id] === "up"}
                                          >
                                            <svg width="13" height="13" viewBox="0 0 24 24" fill={feedbackMap[message.id] === "up" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                              <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
                                              <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                                            </svg>
                                            <span className="sr-only">Helpful</span>
                                          </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>Helpful</TooltipContent>
                                      </Tooltip>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            variant="ghost"
                                            size="icon"
                                            className={cn(
                                              "h-7 w-7 rounded-full transition-all",
                                              feedbackMap[message.id] === "down" && "text-red-500 opacity-100 bg-red-50"
                                            )}
                                            onClick={() => submitFeedback(message.id, "down")}
                                            aria-label="Not helpful"
                                            aria-pressed={feedbackMap[message.id] === "down"}
                                          >
                                            <svg width="13" height="13" viewBox="0 0 24 24" fill={feedbackMap[message.id] === "down" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
                                              <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                                            </svg>
                                            <span className="sr-only">Not helpful</span>
                                          </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>Not helpful</TooltipContent>
                                      </Tooltip>
                                    </>
                                  )}
                                </div>
                              )}
                            </div>
                            {/* Inline disclaimer for Legal / Government Schemes responses */}
                            {message.role === "assistant" &&
                              !message.id?.startsWith("welcome-") &&
                              (selectedDomain === "Legal" || selectedDomain === "Government Schemes") && (
                              <p className="mt-1.5 text-[10px] leading-relaxed text-muted-foreground/60 italic pl-0.5">
                                {selectedDomain === "Legal"
                                  ? "For informational purposes only — not a substitute for advice from a qualified lawyer."
                                  : "Eligibility criteria may vary. Verify details at the official scheme portal before applying."}
                              </p>
                            )}
                            {message.role === "assistant" && message.webSearched && (
                              <span
                                className="mt-1 inline-flex items-center gap-1 text-[10px] text-muted-foreground/70"
                                title="Agent autonomously searched the web to supplement its answer"
                              >
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                                  <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                                </svg>
                                web search
                              </span>
                            )}
                            {message.role === "assistant" && message.routing && (
                              <RoutingTrace routing={message.routing} />
                            )}
                            <span
                              className={cn(
                                "text-[10px] mt-1 text-muted-foreground/80",
                                message.role === "user" ? "text-right pr-1" : "text-left pl-1"
                              )}
                            >
                              {hydrated ? formatTime(message.timestamp) : ""}
                            </span>
                          </div>
                          {message.role === "user" && (
                            <Avatar className="h-9 w-9 ring-2 ring-accent/40 shrink-0">
                              <AvatarFallback className="bg-gradient-to-br from-accent/80 to-secondary text-foreground/80">
                                <SoftUser className="h-5 w-5" />
                              </AvatarFallback>
                            </Avatar>
                          )}
                        </div>
                      );
                    })}
                    {isLoading && !streamingMsgId && (
                      <div className="flex items-end gap-3 justify-start animate-slide-in-left">
                        <Avatar className="h-9 w-9 ring-2 ring-primary/30">
                          <AvatarFallback className="bg-gradient-to-br from-primary/90 to-accent text-primary-foreground">
                            <BlossomLogo className="h-5 w-5" />
                          </AvatarFallback>
                        </Avatar>
                        <div className="rounded-2xl rounded-bl-md px-4 py-3 text-sm bg-card border border-border/40 petal-shadow">
                          <div className="flex items-center gap-1.5">
                            {[0, 1, 2].map((i) => (
                              <span
                                key={i}
                                className="h-2 w-2 rounded-full bg-primary/60"
                                style={{ animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                </ScrollArea>

                {messageCount <= 1 && !isLoading && (
                  <div className="mt-4 px-1">
                    <div className="flex items-center gap-2 mb-2.5">
                      <div className="h-px flex-1 bg-border/40" />
                      <p className="text-[10px] uppercase tracking-widest text-muted-foreground/50 font-medium">
                        Suggested
                      </p>
                      <div className="h-px flex-1 bg-border/40" />
                    </div>
                    <QuickReplies
                      prompts={currentPersona.quickReplies}
                      onSelect={(p) => sendTextMessage(p)}
                      disabled={isLoading}
                    />
                  </div>
                )}

                <div className="mt-4">
                  {/* Hidden file input for document attachment */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.md,.csv,.json,.log,.pdf,.docx"
                    className="sr-only"
                    onChange={handleFileAttach}
                    aria-hidden
                  />

                  {/* Attached file chip */}
                  {attachedContext && (
                    <div className="mb-2 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary/10 border border-primary/25 text-[11px] text-primary">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                      </svg>
                      <span className="flex-1 truncate font-medium">{attachedContext.name}</span>
                      <span className="text-muted-foreground/70">— will be sent with next message</span>
                      <button
                        type="button"
                        onClick={() => setAttachedContext(null)}
                        className="ml-1 rounded-full hover:bg-primary/15 p-0.5 transition"
                        aria-label="Remove attachment"
                      >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  )}

                  <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)}>
                      {/* Unified input pill */}
                      <div className={cn(
                        "flex items-center gap-2 rounded-2xl border px-3 py-2 transition-all duration-300",
                        "bg-card/80 backdrop-blur-sm",
                        "border-border/55 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/15"
                      )}>
                        {/* Mic button */}
                        {voiceSupported && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                type="button"
                                size="icon"
                                aria-label={isListening ? "Stop recording" : "Voice input"}
                                onClick={() => isListening ? stopListening() : startListening()}
                                disabled={isLoading}
                                className={cn(
                                  "shrink-0 h-9 w-9 rounded-xl transition-all duration-300",
                                  isListening
                                    ? "bg-red-500/20 text-red-500 animate-pulse"
                                    : "bg-accent/20 text-accent-foreground hover:bg-accent/35"
                                )}
                              >
                                {isListening
                                  ? <SoftStop className="h-4 w-4" />
                                  : <SoftMic className="h-4 w-4" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {isListening ? "Stop listening" : `Voice input (${LANGS.find(l=>l.code===lang)?.label || lang})`}
                            </TooltipContent>
                          </Tooltip>
                        )}

                        {/* Attach file button */}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              type="button"
                              size="icon"
                              className={cn(
                                "shrink-0 h-9 w-9 rounded-xl transition-all duration-300",
                                attachedContext
                                  ? "bg-primary/20 text-primary"
                                  : "bg-accent/20 text-accent-foreground hover:bg-accent/35"
                              )}
                              onClick={() => fileInputRef.current?.click()}
                              disabled={isLoading}
                              aria-label="Attach a text file as context"
                            >
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                              </svg>
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Attach a file (.txt, .md, .pdf, .docx, .csv)</TooltipContent>
                        </Tooltip>

                        {/* Text input */}
                        <FormField
                          control={form.control}
                          name="message"
                          render={({ field }) => (
                            <FormItem className="flex-grow">
                              <FormControl>
                                <Input
                                  placeholder={isListening
                                    ? (interimTranscript || "Listening…")
                                    : `Message ${currentPersona.persona}...`}
                                  {...field}
                                  value={isListening && interimTranscript ? interimTranscript : field.value}
                                  ref={(el) => { field.ref(el); inputRef.current = el; }}
                                  disabled={isLoading}
                                  maxLength={4000}
                                  className={cn(
                                    "border-0 bg-transparent h-9 px-1 focus-visible:ring-0 focus-visible:ring-offset-0 text-sm",
                                    isListening ? "placeholder:text-primary/70 italic" : "placeholder:text-muted-foreground/50"
                                  )}
                                  autoComplete="off"
                                  readOnly={isListening}
                                />
                              </FormControl>
                            </FormItem>
                          )}
                        />

                        {/* Char counter arc + send */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          {inputValue?.length > 0 && (
                            <span className={cn(
                              "text-[10px] tabular-nums",
                              remaining < 200 ? "text-amber-500 font-semibold" : "text-muted-foreground/40"
                            )}>
                              {remaining}
                            </span>
                          )}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                type="submit"
                                disabled={isLoading || !inputValue?.trim()}
                                size="icon"
                                className="h-9 w-9 rounded-xl bg-gradient-to-br from-primary to-primary/85 text-primary-foreground petal-shadow transition-all duration-300 hover:scale-105 hover:shadow-lg disabled:opacity-40 disabled:hover:scale-100"
                              >
                                <SoftSend className="h-4 w-4" />
                                <span className="sr-only">Send</span>
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Send</TooltipContent>
                          </Tooltip>
                        </div>
                      </div>

                      <p className="mt-1.5 text-center text-[10px] text-muted-foreground/50">
                        {isListening ? "Listening… tap stop when done" : "Enter to send · tap mic for voice"}
                      </p>
                    </form>
                  </Form>
                </div>
              </div>
            </Tabs>

            <AlertDialog
              open={!!pendingDomain}
              onOpenChange={(open) => !open && setPendingDomain(null)}
            >
              <AlertDialogContent className="rounded-3xl border-border/40 bg-card/85 backdrop-blur-xl petal-shadow">
                <AlertDialogHeader>
                  <AlertDialogTitle className="flex items-center gap-2 font-headline">
                    <SoftAlert className="h-5 w-5 text-primary" />
                    Switch to {pendingDomain ? domainConfig[pendingDomain].persona : ""}?
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    Your current chat will stay in {currentPersona.persona}'s history.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="rounded-full" onClick={() => setPendingDomain(null)}>
                    Cancel
                  </AlertDialogCancel>
                  <AlertDialogAction
                    className="rounded-full bg-gradient-to-br from-primary to-primary/85"
                    onClick={() => pendingDomain && handleDomainSwitch(pendingDomain)}
                  >
                    Switch
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>

            <ChatHistoryDrawer
              open={historyOpen}
              onOpenChange={setHistoryOpen}
              persona={currentPersona.persona}
              domain={selectedDomain}
              sessions={currentDomainState.sessions}
              activeId={currentDomainState.activeId}
              onSelect={selectSession}
              onDelete={deleteSession}
              onNew={startNewChat}
            />

            <EligibilityChecker open={eligOpen} onOpenChange={setEligOpen} />
          </CardContent>
        </Card>
      </div>

    </TooltipProvider>
  );
}
