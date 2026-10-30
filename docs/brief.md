# Brief

The take-home challenge brief as received ("Code Challenge 28 Oct.pdf"), converted to Markdown. Wording is unchanged.

## Take-home Code Challenge: Commission Quote App

Welcome, and thanks for interviewing with us

We’d like you to complete a short take-home coding challenge so we can get a feel for how you approach coding, engineering decisions and problem solving.

We know your time is valuable, so we’ve intentionally kept the scope narrow.

## Timebox

Please aim to spend around 4 hours on this challenge. We want to see readable code, a working solution, core tests, clear edge-case handling, and simple instructions for running it. Also treat this as the foundation of a real app.

If there are things you would improve with more time, feel free to mention them in your README.

## Context

In our Lending Platform, staff members frequently need to generate "Commission Quotes" based on loan applications. To do this, our system needs to process loan details and send them to an external third-party vendor Commission Quote API, which calculates the commission and returns a quote.

Currently, the external third-party vendor Commission Quote API is under construction and not yet available. However, the API contract and authentication requirements have been finalized. We need to unblock our development by building our application against a mock version of this API.

## Your task

Your task is to build a web application that allows a user to input loan details and displays the generated commission quote, along with a mock version of this third-party vendor Commission Quote API that simulates the external vendor.

### 1. Web application requirements

- A user interface with a form to capture basic loan details (e.g., `loanAmount`, `loanTermInMonths`, `riskBand`).
- A "Generate Quote" button.
- A display area to show the resulting quote data when the request is successful.
- Proper loading states and error messages if the quote generation fails.

### 2. Third-party vendor Commission Quote API requirements

- **Contract:** It must accept and return data based on this agreed contract:
  - Request payload: `loanAmount`, `loanTermInMonths`, `riskBand` (`LOW`, `MEDIUM`, `HIGH`)
  - Response payload: `quoteId`, `commissionRate`, `totalCommission`
- **Security:** The third-party vendor Commission Quote API is strictly secured. It must require an `api-key` header to process the request. Any request without a valid API key should be rejected.
- **Simulation:** To mimic real-world network conditions, your Commission Quote API must occasionally (randomly) throw an error.

## AI usage

We recognise that modern software engineering involves leveraging AI tools (e.g., GitHub Copilot, ChatGPT, Gemini, Claude). Using AI is fully allowed and encouraged during this take-home challenge.

However, we expect the following:

- **Transparency:** Please include a brief section in your `README.md` outlining how you utilised AI during the challenge (e.g., "Used Copilot to generate boilerplate UI components," "Used ChatGPT to write regex/tests," or "Generated the initial Mock API structure with Claude").
- **Comprehension:** You must take full ownership of the code you submit. You should deeply understand how it works, why it was structured that way, and its potential trade-offs.
- **Next stage:** If successful, the next stage is a collaborative live-coding session where we will expand this exact codebase. You are welcome to use AI collaboratively with us during that session, and we will likely ask you to walk us through the code you (or the AI) wrote.

## What we'll look at

### Must-haves

- **Solve the core problem correctly:** The web application successfully captures input, securely communicates with the Commission Quote API, and gracefully handles the response (both success and failure).
- **Keep the code readable and structured clearly:** We look for sensible directory structures, clean abstractions, and good separation of concerns.
- **Include core tests:** We don't need 100% coverage, but please include a few unit or integration tests for the ones you think matter most.
- **Handle key edge cases:** What happens if the user submits invalid numbers? What happens when the Commission Quote API times out or throws an error?
- **Use appropriate security and API handling:** Consider the security of the integration and how errors and authentication should be handled.
- **Make sensible code decisions:** Treat this as the foundation of a real app. Choose a tech stack you are most comfortable with.
- **Follow good engineering practices:** Approach this challenge as you would a real development task.
- **Include run instructions:** Provide a `README.md` with clear, step-by-step instructions on how to start the application components and run the tests.

### Nice-to-haves

- **UI Polish:** A clean, accessible and responsive UI is appreciated, but UI polish is not a core part of the assessment. Using basic CSS or a component library is completely fine.

## Submission

Please send us either:

- a link to a public or private GitHub repository, or
- a zip file containing the project

We aim to review submissions and get back to you with feedback and next steps within 48 hours.

If you progress, we’ll use this codebase as the starting point for the Live Pair Programming interview.

Good luck, and have fun!
