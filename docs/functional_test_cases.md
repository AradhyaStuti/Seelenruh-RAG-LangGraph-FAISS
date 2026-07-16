# Functional Test Cases and Evaluation Notes

This document records a short functional test matrix for the Seelenruh project. The cases below focus on the main user journeys that matter in the current app: persona routing, session handling, feedback, source display, and admin access.

## Functional test matrix

The executable pytest suite in [server/tests/test_functional_cases.py](server/tests/test_functional_cases.py) currently contains 26 runnable checks.

| Test ID | Scenario | Expected result |
|---|---|---|
| TC-01 | Legal query | The assistant routes to the legal persona and returns guidance with relevant citations. |
| TC-02 | Persona switch | The UI and assistant move from legal to government-scheme mode correctly. |
| TC-03 | Empty input | The app shows a validation message and does not send a blank request. |
| TC-04 | Missing or invalid session | A new session is created gracefully without crashing. |
| TC-05 | Feedback submission | Feedback is accepted and stored without breaking the current workflow. |
| TC-06 | Source panel | Retrieved sources appear in a readable format after a response is returned. |
| TC-07 | Network failure | The app shows a friendly error state and preserves the user context. |
| TC-08 | Mobile layout | The interface remains usable on a narrow viewport. |
| TC-09 | Hindi query | The response remains understandable and keeps the language context intact. |
| TC-10 | Hinglish query | The assistant replies in a natural hybrid style. |
| TC-11 | Emergency or danger signal | The assistant prioritises immediate safety steps and helpline information. |
| TC-12 | Government-scheme query | The assistant routes to the schemes domain and provides eligibility-related guidance. |
| TC-13 | Logout during an active session | The session is cleared cleanly and the user is returned to the login state. |
| TC-14 | Save a response | The saved moment appears in the relevant history view without duplication. |
| TC-15 | Load history | Prior messages are shown in order and the conversation stays intact. |
| TC-16 | Clear chat | The visible history is reset safely. |
| TC-17 | File upload | The upload flow accepts the file and shows a success or validation message. |
| TC-18 | Unsupported file type | The app rejects the file with a clear validation message. |
| TC-19 | Authorized admin access | The admin dashboard loads and shows the expected sections. |
| TC-20 | Unauthorized admin access | Access is denied and the user receives an appropriate error message. |
| TC-21 | Source citation click | The cited source details expand or open correctly. |
| TC-22 | Retry after transient failure | The request is retried gracefully once the issue clears. |
| TC-23 | Long prompt | The system responds without crashing and preserves the main content. |
| TC-24 | Multi-part legal question | The assistant handles the query in a structured way. |
| TC-25 | Unsafe or out-of-scope request | The assistant refuses or redirects safely. |
| TC-26 | Follow-up question | The assistant uses earlier context and maintains continuity. |

## Evaluation notes

The repository also includes evaluation scripts and benchmark outputs for response quality, routing, retrieval, and latency. These are useful for reviewing the current behaviour of the assistant under repeated prompts, but the numbers should be read as project-specific measurements rather than universal benchmarks.
