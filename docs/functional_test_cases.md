# Functional Test Cases

This file is basically my checklist for testing Seelenruh before deployment. Every time I added a new feature or changed something important, I used these cases to make sure I hadn't broken an existing flow. The focus is on the core parts of the project like persona routing, session management, feedback, source citations, and admin access.

## Test Matrix

The actual automated tests are in [server/tests/test_functional_cases.py](server/tests/test_functional_cases.py). At the moment, there are 26 functional test cases covering the main features of the application.

| Test ID | Scenario                       | Expected Result                                                                           |
| ------- | ------------------------------ | ----------------------------------------------------------------------------------------- |
| TC-01   | Legal query                    | Routes the request to the legal assistant and returns a response with relevant citations. |
| TC-02   | Persona switch                 | Changes from the legal assistant to the government schemes assistant without issues.      |
| TC-03   | Empty input                    | Shows a validation message instead of sending an empty request.                           |
| TC-04   | Missing or invalid session     | Creates a new session automatically without crashing the app.                             |
| TC-05   | Feedback submission            | Saves user feedback successfully without interrupting the conversation.                   |
| TC-06   | Source panel                   | Displays the retrieved sources clearly after a response is generated.                     |
| TC-07   | Network failure                | Shows a user-friendly error message while keeping the current conversation intact.        |
| TC-08   | Mobile layout                  | Interface remains usable and responsive on smaller screens.                               |
| TC-09   | Hindi query                    | Responds correctly in Hindi while maintaining context.                                    |
| TC-10   | Hinglish query                 | Responds naturally in Hinglish.                                                           |
| TC-11   | Emergency or danger signal     | Prioritizes immediate safety guidance and relevant helpline information.                  |
| TC-12   | Government scheme query        | Routes to the schemes assistant and provides eligibility guidance.                        |
| TC-13   | Logout during active session   | Clears the session and returns the user to the login screen.                              |
| TC-14   | Save a response                | Saved response appears in history without creating duplicates.                            |
| TC-15   | Load history                   | Previous conversations load correctly and stay in order.                                  |
| TC-16   | Clear chat                     | Clears the conversation history safely.                                                   |
| TC-17   | File upload                    | Accepts supported files and shows a confirmation or validation message.                   |
| TC-18   | Unsupported file type          | Rejects unsupported files with a clear error message.                                     |
| TC-19   | Authorized admin access        | Opens the admin dashboard successfully.                                                   |
| TC-20   | Unauthorized admin access      | Denies access with an appropriate error message.                                          |
| TC-21   | Source citation click          | Opens or expands the selected citation correctly.                                         |
| TC-22   | Retry after transient failure  | Retries the request successfully after a temporary failure.                               |
| TC-23   | Long prompt                    | Handles long prompts without crashing or losing important context.                        |
| TC-24   | Multi-part legal question      | Returns a structured response covering all parts of the question.                         |
| TC-25   | Unsafe or out-of-scope request | Responds safely by refusing or redirecting the request where appropriate.                 |
| TC-26   | Follow-up question             | Uses earlier conversation context to answer naturally.                                    |

## Notes

Apart from these functional tests, I also built a separate evaluation setup to check things like response quality, routing accuracy, retrieval performance, and latency. I mainly used those while making changes to the project so I could compare results before and after an update. They're useful for catching regressions, but I don't treat them as universal benchmarks since they're specific to this project and its datasets.
