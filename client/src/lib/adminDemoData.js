// Demo / seed data shown when the backend has no real data yet.
// Each page checks: if API returned empty, use this as fallback.

export const DEMO_ANALYTICS = {
  total_documents: 47,
  active_chunks: 312,
  open_gaps: 7,
  total_queries: 1247,
  total_feedback: 112,
  feedback_summary: { upvotes: 89, downvotes: 23 },
  feedback_by_domain: [
    { domain: "Usha",    upvotes: 45, downvotes: 8  },
    { domain: "Umang",   upvotes: 22, downvotes: 6  },
    { domain: "Aarogya", upvotes: 18, downvotes: 7  },
    { domain: "Raksha",  upvotes: 4,  downvotes: 2  },
  ],
  confidence_distribution: {
    High:   420,
    Medium: 580,
    Low:    180,
    None:   67,
  },
  gaps_by_domain: [
    { domain: "Usha",    open: 3, solved: 8,  ignored: 2 },
    { domain: "Umang",   open: 2, solved: 5,  ignored: 1 },
    { domain: "Aarogya", open: 1, solved: 11, ignored: 0 },
    { domain: "Raksha",  open: 1, solved: 3,  ignored: 1 },
  ],
  recent_uploads: [
    { id: "d1", filename: "mental_health_basics.pdf",   domain: "Usha",    chunk_count: 28, file_type: "pdf",  status: "active", indexed_at: "2026-07-10T09:14:00Z" },
    { id: "d2", filename: "tenant_rights_india.pdf",    domain: "Umang",   chunk_count: 41, file_type: "pdf",  status: "active", indexed_at: "2026-07-08T14:30:00Z" },
    { id: "d3", filename: "pm_jan_arogya_yojana.md",   domain: "Aarogya", chunk_count: 19, file_type: "md",   status: "active", indexed_at: "2026-07-07T11:00:00Z" },
    { id: "d4", filename: "domestic_violence_act.txt",  domain: "Raksha",  chunk_count: 14, file_type: "txt",  status: "active", indexed_at: "2026-07-05T16:45:00Z" },
    { id: "d5", filename: "anxiety_cbt_guide.pdf",      domain: "Usha",    chunk_count: 33, file_type: "pdf",  status: "active", indexed_at: "2026-07-03T08:20:00Z" },
    { id: "d6", filename: "consumer_protection.docx",   domain: "Umang",   chunk_count: 22, file_type: "docx", status: "active", indexed_at: "2026-07-01T12:00:00Z" },
    { id: "d7", filename: "pradhan_mantri_awas.pdf",    domain: "Aarogya", chunk_count: 17, file_type: "pdf",  status: "active", indexed_at: "2026-06-28T10:30:00Z" },
    { id: "d8", filename: "cyber_crime_helpline.txt",   domain: "Raksha",  chunk_count: 9,  file_type: "txt",  status: "active", indexed_at: "2026-06-25T15:00:00Z" },
  ],
};

export const DEMO_STATUS = {
  status: "ok",
  rag_status: "ok",
  faiss_size: 312,
  total_documents: 47,
  chunk_count: 312,
};

export const DEMO_AUDIT_LOG = [
  { id: "a1", timestamp: "2026-07-17T10:45:00Z", action: "document_upload",  detail: "mental_health_basics.pdf indexed (28 chunks)",    user: "admin" },
  { id: "a2", timestamp: "2026-07-16T14:20:00Z", action: "knowledge_gap",    detail: "New gap flagged in Umang domain",                  user: "system" },
  { id: "a3", timestamp: "2026-07-15T09:30:00Z", action: "document_upload",  detail: "tenant_rights_india.pdf indexed (41 chunks)",      user: "admin" },
  { id: "a4", timestamp: "2026-07-14T16:00:00Z", action: "gap_resolved",     detail: "Gap #12 marked as solved",                        user: "admin" },
  { id: "a5", timestamp: "2026-07-13T11:15:00Z", action: "index_rebuild",    detail: "FAISS index rebuilt — 312 vectors",               user: "system" },
  { id: "a6", timestamp: "2026-07-12T08:45:00Z", action: "document_upload",  detail: "pm_jan_arogya_yojana.md indexed (19 chunks)",     user: "admin" },
  { id: "a7", timestamp: "2026-07-11T13:00:00Z", action: "snapshot_created", detail: "Index snapshot v3 created",                       user: "system" },
  { id: "a8", timestamp: "2026-07-10T17:30:00Z", action: "feedback_export",  detail: "Feedback CSV exported (112 entries)",             user: "admin" },
  { id: "a9", timestamp: "2026-07-09T10:00:00Z", action: "document_delete",  detail: "outdated_schemes_2022.pdf soft deleted",          user: "admin" },
  { id: "a10",timestamp: "2026-07-08T14:30:00Z", action: "document_upload",  detail: "domestic_violence_act.txt indexed (14 chunks)",   user: "admin" },
];

export const DEMO_SNAPSHOTS = [
  { id: "s1", label: "Snapshot v4 (current)", timestamp: "2026-07-13T11:15:00Z", chunk_count: 312 },
  { id: "s2", label: "Snapshot v3",            timestamp: "2026-07-07T09:00:00Z", chunk_count: 290 },
  { id: "s3", label: "Snapshot v2",            timestamp: "2026-06-30T15:30:00Z", chunk_count: 261 },
  { id: "s4", label: "Snapshot v1",            timestamp: "2026-06-20T10:00:00Z", chunk_count: 198 },
];

export const DEMO_FEEDBACK_STATS = {
  total_votes: 112,
  upvotes: 89,
  downvotes: 23,
  by_domain: [
    { domain: "Usha",    upvotes: 45, downvotes: 8,  total: 53 },
    { domain: "Umang",   upvotes: 22, downvotes: 6,  total: 28 },
    { domain: "Aarogya", upvotes: 18, downvotes: 7,  total: 25 },
    { domain: "Raksha",  upvotes: 4,  downvotes: 2,  total: 6  },
  ],
};

export const DEMO_DOCUMENTS = [
  { id: "d1", filename: "mental_health_basics.pdf",   domain: "Mental Health",      file_type: "pdf",  chunk_count: 28, file_size: 204800,  status: "active",  indexed_at: "2026-07-10T09:14:00Z", language: "en", topic: "Anxiety, Depression", source: "NIMHANS" },
  { id: "d2", filename: "tenant_rights_india.pdf",    domain: "Legal",              file_type: "pdf",  chunk_count: 41, file_size: 358400,  status: "active",  indexed_at: "2026-07-08T14:30:00Z", language: "en", topic: "Tenant Rights", source: "MoHUA" },
  { id: "d3", filename: "pm_jan_arogya_yojana.md",   domain: "Government Schemes", file_type: "md",   chunk_count: 19, file_size: 51200,   status: "active",  indexed_at: "2026-07-07T11:00:00Z", language: "en", topic: "Health Insurance", source: "NHA" },
  { id: "d4", filename: "domestic_violence_act.txt",  domain: "Safety",             file_type: "txt",  chunk_count: 14, file_size: 40960,   status: "active",  indexed_at: "2026-07-05T16:45:00Z", language: "en", topic: "PWDVA 2005", source: "MoWCD" },
  { id: "d5", filename: "anxiety_cbt_guide.pdf",      domain: "Mental Health",      file_type: "pdf",  chunk_count: 33, file_size: 296000,  status: "active",  indexed_at: "2026-07-03T08:20:00Z", language: "en", topic: "CBT Techniques", source: "APA" },
  { id: "d6", filename: "consumer_protection.docx",   domain: "Legal",              file_type: "docx", chunk_count: 22, file_size: 163840,  status: "active",  indexed_at: "2026-07-01T12:00:00Z", language: "en", topic: "Consumer Rights", source: "MoCA" },
  { id: "d7", filename: "pradhan_mantri_awas.pdf",    domain: "Government Schemes", file_type: "pdf",  chunk_count: 17, file_size: 122880,  status: "active",  indexed_at: "2026-06-28T10:30:00Z", language: "en", topic: "Housing Scheme", source: "MoHUA" },
  { id: "d8", filename: "cyber_crime_helpline.txt",   domain: "Safety",             file_type: "txt",  chunk_count: 9,  file_size: 20480,   status: "active",  indexed_at: "2026-06-25T15:00:00Z", language: "en", topic: "Cybercrime", source: "MHA" },
  { id: "d9", filename: "grief_support_hindi.pdf",    domain: "Mental Health",      file_type: "pdf",  chunk_count: 21, file_size: 184320,  status: "active",  indexed_at: "2026-06-20T09:00:00Z", language: "hi", topic: "Grief & Loss", source: "iCall" },
  { id: "d10",filename: "ipc_sections_summary.pdf",   domain: "Legal",              file_type: "pdf",  chunk_count: 38, file_size: 327680,  status: "deleted", indexed_at: "2026-06-15T14:00:00Z", language: "en", topic: "IPC", source: "MoLJ" },
];

export const DEMO_KNOWLEDGE_GAPS = [
  { id: "g1",  query: "What are the steps to file an FIR online in Maharashtra?",        domain: "Legal",              confidence: "Low",    status: "open",    created_at: "2026-07-16T10:00:00Z" },
  { id: "g2",  query: "Can I get PM-KISAN if I'm a tenant farmer?",                      domain: "Government Schemes", confidence: "Low",    status: "open",    created_at: "2026-07-15T09:30:00Z" },
  { id: "g3",  query: "What is the difference between OCD and anxiety disorder?",         domain: "Mental Health",      confidence: "Medium", status: "open",    created_at: "2026-07-14T14:00:00Z" },
  { id: "g4",  query: "How do I get a stalking protection order?",                        domain: "Safety",             confidence: "Low",    status: "open",    created_at: "2026-07-13T11:00:00Z" },
  { id: "g5",  query: "What documents do I need for Ayushman Bharat registration?",       domain: "Government Schemes", confidence: "Medium", status: "open",    created_at: "2026-07-12T08:00:00Z" },
  { id: "g6",  query: "Is verbal abuse covered under domestic violence law?",             domain: "Legal",              confidence: "Medium", status: "open",    created_at: "2026-07-11T16:00:00Z" },
  { id: "g7",  query: "How long does PMAY application take to process?",                  domain: "Government Schemes", confidence: "Low",    status: "open",    created_at: "2026-07-10T12:00:00Z" },
  { id: "g8",  query: "How do I stop intrusive thoughts at night?",                       domain: "Mental Health",      confidence: "High",   status: "solved",  created_at: "2026-07-09T09:00:00Z" },
  { id: "g9",  query: "What is the helpline number for senior citizens?",                 domain: "Safety",             confidence: "Low",    status: "solved",  created_at: "2026-07-08T14:00:00Z" },
  { id: "g10", query: "Can I get legal aid for free if I can't afford a lawyer?",         domain: "Legal",              confidence: "Medium", status: "solved",  created_at: "2026-07-07T10:00:00Z" },
  { id: "g11", query: "What are signs of burnout vs depression?",                         domain: "Mental Health",      confidence: "Medium", status: "ignored", created_at: "2026-07-06T11:00:00Z" },
  { id: "g12", query: "Is the Right to Information Act applicable to private companies?", domain: "Legal",              confidence: "Low",    status: "ignored", created_at: "2026-07-05T09:00:00Z" },
];
