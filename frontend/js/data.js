/* Fixtures for the minimal demo: one pull request, two tasks on the same concept, the scoring standard, and stand-in
   answers for the presenter. Everything here is synthetic: the company, the code, the customers and the invoices. */
window.Viva = window.Viva || {};
Viva.data = {
  // The company the demo runs in (a made-up payments company), and the person using it. The avatar file is assets/avatar.jpg.
  org: { name: 'Harbourpay', team: 'Billing Engineering' },
  me: { name: 'Tony', role: 'Graduate engineer', avatar: 'assets/avatar.jpg' },
  // The senior assigned to review this team's checks. A demo identity: the reviewer page is opened by a token, not SSO.
  reviewer: { name: 'Priya Raman', role: 'Senior engineer, Billing' },
  // Default pull request. The GitHub link can override these fields through the URL (see app.js).
  pr: {
    repo: 'harbourpay/billing', number: 214, title: 'Let customers download their invoices',
    author: 'tony', branch: 'tony/invoice-download', base: 'main', sha: 'b7e21f4',
    files: [{ name: 'invoices.py', add: 41, del: 0 }, { name: 'test_invoices.py', add: 36, del: 0 }]
  },
  // Other checks on the same commit, shown in the GitHub preview. They all pass: the tests only ever ask as one customer.
  ci: [{ name: 'ci / unit-tests', note: 'Passed in 1m 04s' }, { name: 'ci / lint', note: 'Passed in 16s' }],
  maxAttempts: 2,
  maxTurns: 3,
  standardTurns: 2,
  minAnswerChars: 20,
  clipSeconds: 180,
  vivaPass: 2, // rubric points the viva needs, on top of all three code checks

  // Two tasks on the same concept: the first attempt reads list_invoices (it has a hole), the retake reads invoice_pdf
  // (it is right), so the retake is a new artifact and not the same question again.
  // Each task: the code and its tests, three checks with one right answer each (decided here, never by a model), what
  // really happens when it runs, the viva questions, the rubric the viva is assessed against, and stand-in answers.
  // rubric[].sim: patterns that must all match one sentence; the simulated viva uses them when the model is unavailable.
  sets: [
    {
      task: {
        fn: 'list_invoices', file: 'invoices.py',
        code: `@router.get("/invoices")
def list_invoices(customer_id: int, user: User = Depends(current_user)):
    rows = db.execute(
        "SELECT id, amount, status FROM invoices WHERE customer_id = :cid",
        {"cid": customer_id},
    )
    return [dict(r) for r in rows]`,
        tests: [
          { id: 'test_list_invoices_returns_own', note: 'Customer 42 asks for customer 42 and gets 2 invoices.' },
          { id: 'test_requires_login', note: 'No token: 401.' },
          { id: 'test_amounts_are_decimal', note: 'Amounts come back as exact decimals.' },
          { id: 'test_new_customer_gets_empty_list', note: 'A customer with no invoices gets [].' }
        ],
        rule: 'A customer can only see their own invoices.',
        items: {
          behaviour: {
            q: 'Customer 42 is logged in and calls `GET /invoices?customer_id=17`. What comes back?',
            options: [{ id: '401', text: '401 Unauthorized' }, { id: '403', text: '403 Forbidden' }, { id: 'empty', text: 'An empty list' }, { id: 'others', text: "Customer 17's invoices" }],
            correct: 'others'
          },
          requirement: {
            q: 'Does this endpoint meet the rule?',
            options: [{ id: 'yes', text: 'Yes, it meets the rule' }, { id: 'no', text: 'No, it breaks the rule' }],
            correct: 'no'
          },
          evidence: {
            q: 'Which test backs up your answer to question 1?',
            options: [
              { id: 'test_list_invoices_returns_own', text: 'test_list_invoices_returns_own' }, { id: 'test_requires_login', text: 'test_requires_login' },
              { id: 'test_amounts_are_decimal', text: 'test_amounts_are_decimal' }, { id: 'none', text: "None of them asks for another customer's invoices" }
            ],
            correct: 'none'
          }
        },
        // What running it on synthetic data shows (simulated in this demo), and the facts the viva assessment may use.
        reveal: {
          request: 'GET /invoices?customer_id=17', as: 'Logged in as customer 42',
          status: '200 OK', result: "Customer 17's invoices",
          rows: [['INV-1703', 'AUD 1,240.00', 'paid'], ['INV-1711', 'AUD 385.50', 'due'], ['INV-1729', 'AUD 2,016.00', 'due']],
          owner: 'All three belong to Northwind Pty Ltd, customer 17.',
          note: 'This is broken access control, OWASP’s number one risk in 2025. The same class of bug left 170 of 1,645 AI-built apps readable by anyone (CVE-2025-48757).'
        },
        facts: 'Logged in as customer 42, GET /invoices?customer_id=17 returned 200 OK with three invoices that belong to customer 17 (Northwind Pty Ltd). The endpoint checks that someone is logged in, through current_user, but never compares user.customer_id with the customer_id in the request, which the caller chooses.',
        leak: ['Northwind', 'INV-1703', "17's invoices", '200 OK', 'returns their invoices'],
        retake: 'Fix list_invoices, then take a new task on the same idea. This miss stays private, and your level does not change.'
      },
      questions: {
        implementation: { label: 'How it works', text: 'Walk us through how list_invoices decides whose invoices to return.' },
        rationale: { label: 'Why this way', text: 'Where does the customer id in this request come from, and why take it from there?' }
      },
      // Template follow-ups, used when the model is not available or its question is filtered out.
      probes: {
        specific: { label: 'Be concrete', text: 'Give one request and say exactly what list_invoices returns for it.' },
        reasoning: { label: 'What could go wrong', text: 'If someone else controlled this request, what would they change first?' }
      },
      rubric: [
        { id: 'source', text: 'Says the customer id comes from the request, which the caller controls.', sim: ['customer[_ ]id', 'query|request|url|parameter|caller|client'] },
        { id: 'login', text: 'Says the endpoint checks that someone is logged in, but never compares that login with the customer asked for.', sim: ['current_user|logged in|login|token|session', "never|not|doesn't|does not|without|only"] },
        { id: 'harm', text: "Names the consequence or the fix: any logged-in customer can read another customer's invoices; take the id from the login instead.", sim: ["another customer|other customer|any customer|someone else|from the session|from the login"] }
      ],
      answers: {
        specific: {
          implementation: 'list_invoices takes customer_id from the query string, so the caller chooses it. It runs the SELECT for whatever id comes in and returns those rows.',
          rationale: 'It checks that someone is logged in through current_user, but it never compares user.customer_id with the id in the URL. So customer 42 can ask for customer_id=17 and read another customer\'s invoices. I should take the id from the session instead.',
          probe: 'As customer 42, GET /invoices?customer_id=17 returns the invoices of customer 17, because nothing ties the id to the login.'
        },
        generic: {
          implementation: 'The endpoint returns the invoices in a clean and secure way. It follows best practices and uses the database properly, so the right invoices are returned.',
          rationale: 'I built it this way because it is a standard and scalable approach, and authentication makes sure everything is secure.',
          probe: 'It works correctly in every case and follows the standard approach.'
        }
      }
    },
    {
      task: {
        fn: 'invoice_pdf', file: 'invoices.py',
        code: `@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, user: User = Depends(current_user)):
    inv = db.get(Invoice, invoice_id)
    if inv is None or inv.customer_id != user.customer_id:
        raise HTTPException(status_code=404)
    return render_pdf(inv)`,
        tests: [
          { id: 'test_owner_gets_pdf', note: 'Customer 42 asks for their own invoice and gets the PDF.' },
          { id: 'test_other_customer_gets_404', note: "Customer 42 asks for invoice 1703, customer 17's: 404." },
          { id: 'test_requires_login', note: 'No token: 401.' },
          { id: 'test_pdf_shows_total', note: 'The PDF shows the invoice total.' }
        ],
        rule: 'A customer can only see their own invoices.',
        items: {
          behaviour: {
            q: 'Customer 42 is logged in and requests `GET /invoices/1703/pdf`. Invoice 1703 belongs to customer 17. What comes back?',
            options: [{ id: 'pdf', text: 'The PDF of invoice 1703' }, { id: '403', text: '403 Forbidden' }, { id: '404', text: '404 Not Found' }, { id: '500', text: '500 Server Error' }],
            correct: '404'
          },
          requirement: {
            q: 'Does this endpoint meet the rule?',
            options: [{ id: 'yes', text: 'Yes, it meets the rule' }, { id: 'no', text: 'No, it breaks the rule' }],
            correct: 'yes'
          },
          evidence: {
            q: 'Which test backs up your answer to question 1?',
            options: [
              { id: 'test_owner_gets_pdf', text: 'test_owner_gets_pdf' }, { id: 'test_other_customer_gets_404', text: 'test_other_customer_gets_404' },
              { id: 'test_requires_login', text: 'test_requires_login' }, { id: 'none', text: "None of them asks for another customer's invoice" }
            ],
            correct: 'test_other_customer_gets_404'
          }
        },
        reveal: {
          request: 'GET /invoices/1703/pdf', as: 'Logged in as customer 42',
          status: '404 Not Found', result: 'No PDF. The invoice belongs to customer 17.',
          rows: [],
          owner: 'Invoice 1703 belongs to Northwind Pty Ltd, customer 17.',
          note: ''
        },
        facts: 'Logged in as customer 42, GET /invoices/1703/pdf returned 404 Not Found. Invoice 1703 belongs to customer 17. The endpoint compares inv.customer_id with user.customer_id from the login session and returns 404 when they differ or the invoice does not exist; test_other_customer_gets_404 covers this case.',
        leak: ['404', 'Not Found', 'test_other_customer_gets_404'],
        retake: ''
      },
      questions: {
        implementation: { label: 'How it works', text: 'Walk us through what invoice_pdf does between the request and the PDF.' },
        rationale: { label: 'Why this way', text: 'Why does this endpoint answer the way it does when the invoice is not yours?' }
      },
      probes: {
        specific: { label: 'Be concrete', text: 'Name one request that gets the PDF and one that does not, and why.' },
        reasoning: { label: 'How you know', text: 'How would you prove this works for a customer who is not the owner?' }
      },
      rubric: [
        { id: 'owner', text: 'Says the invoice is loaded by its id, and its owner is compared with the customer in the login session.', sim: ['customer_id|owner|belongs', 'session|user\\.customer_id|login|logged'] },
        { id: 'not-found', text: 'Explains why it answers 404 rather than 403: it does not reveal that the invoice exists.', sim: ['404|not found', 'exist|reveal|leak|guess'] },
        { id: 'test', text: 'Names the test that proves another customer is refused, or says how they would test it.', sim: ['test_\\w+|a test|the test|tested', 'other customer|another customer|customer 17'] }
      ],
      answers: {
        specific: {
          implementation: 'invoice_pdf loads the invoice by invoice_id, then compares inv.customer_id with user.customer_id from the login session. If they differ, or the invoice is missing, it raises 404. So customer 42 asking for invoice 1703, which belongs to customer 17, gets 404 and never sees the PDF.',
          rationale: 'It answers 404 instead of 403 because a 403 would tell the caller that invoice 1703 exists, and then invoice numbers can be guessed. The customer id comes from the session, never from the request. The test test_other_customer_gets_404 checks that another customer is refused.',
          probe: 'test_other_customer_gets_404 logs in as customer 42 and asks for invoice 1703 from customer 17, and expects 404. If someone removed the owner check, that test would fail.'
        },
        generic: {
          implementation: 'The endpoint returns the PDF securely and handles errors properly. It follows best practices for this kind of feature.',
          rationale: 'It was the most efficient and maintainable choice. Overall it is a well-structured and robust solution.',
          probe: 'It works correctly and follows the standard approach in every case.'
        }
      }
    }
  ],

  // The scoring standard. A senior-reviewed check adds Risk x Novelty x Gap points to the portfolio (1 to 27).
  // Risk and Novelty are fixed for this pull request; Gap follows the person's level on the concept (see sim.js).
  scoring: {
    max: 27,
    concept: { name: 'Access control: whose data', start: 1 },
    r: 3,
    n: 1,
    why: { r: 'Customer data and sign-in: this change decides who sees invoices.', n: 'You changed the billing service in an earlier pull request.' },
    rows: [
      { key: 'r', name: 'Risk', ask: 'What a mistake costs', levels: ['Internal tool, copy, or behind a switch', 'Ordinary business logic or a public API change', 'Money flow, sign-in, personal data or compliance'] },
      { key: 'n', name: 'Novelty', ask: 'How new this is to you', levels: ['You changed this module before', 'Familiar module with a new way of changing it, or the reverse', 'First time in this module, or a new dependency'] },
      { key: 'g', name: 'Gap', ask: 'How little you have proven', levels: ['Concept level 3: proven more than once', 'Concept level 2: proven once', 'Concept level 0 or 1: not proven yet'] }
    ],
    bands: [
      { key: 'skip', name: 'Skip', from: 1, to: 3, note: 'No interview. About one change in twenty is still checked.' },
      { key: 'light', name: 'Light', from: 4, to: 8, note: 'One question.' },
      { key: 'standard', name: 'Standard', from: 9, to: 17, note: 'Two to three questions.' },
      { key: 'full', name: 'Full', from: 18, to: 27, note: 'Standard questions, and a senior always looks.' }
    ]
  },

  // Presenter shortcuts for the three checks: a confident wrong prediction, and the right one.
  predictions: [
    { wrong: { behaviour: '403', requirement: 'yes', evidence: 'test_requires_login', confidence: 'high' }, right: { behaviour: 'others', requirement: 'no', evidence: 'none', confidence: 'medium' } },
    { wrong: { behaviour: 'pdf', requirement: 'no', evidence: 'test_owner_gets_pdf', confidence: 'high' }, right: { behaviour: '404', requirement: 'yes', evidence: 'test_other_customer_gets_404', confidence: 'high' } }
  ],

  // Illustration for the portfolio trend: dashed, labelled SYNTHETIC, never stored and never counted in any score.
  syntheticHistory: [41, 38, 45, 44, 50, 49, 55, 58, 57, 63, 66, 64, 71, 75]
};
