/* Fixtures for the minimal demo: one pull request, two sets of questions, the scoring standard, and stand-in answers for the presenter. */
window.Viva = window.Viva || {};
Viva.data = {
  // The company the demo runs in (a made-up payments company), and the person using it. The avatar file is assets/avatar.jpg.
  org: { name: 'Harbourpay', team: 'Payments Engineering' },
  me: { name: 'Tony', role: 'Graduate engineer', avatar: 'assets/avatar.jpg' },
  // The senior assigned to review this team's checks. A demo identity: the reviewer page is opened by a token, not SSO.
  reviewer: { name: 'Priya Raman', role: 'Senior engineer, Payments' },
  // Default pull request. The GitHub link can override these fields through the URL (see app.js).
  pr: {
    repo: 'harbourpay/transfers', number: 128, title: 'Charge a transfer fee: 1%, minimum 2.00, cap 25.00',
    author: 'tony', branch: 'tony/transfer-fee', base: 'main', sha: 'a41c9e2',
    files: [{ name: 'fees.py', add: 34, del: 2 }, { name: 'test_fees.py', add: 58, del: 0 }]
  },
  // Other checks on the same commit, shown in the GitHub preview. CI judges correctness; Viva does not.
  ci: [{ name: 'ci / unit-tests', note: 'Passed in 1m 12s' }, { name: 'ci / lint', note: 'Passed in 18s' }],
  maxAttempts: 2,
  maxTurns: 3,
  standardTurns: 2,
  minAnswerChars: 20,
  clipSeconds: 180,

  // Two question sets: the first attempt uses the first, the retake uses the second, so no question repeats.
  // Each set asks what the code does and why it was built that way. Code correctness is not judged.
  // A follow-up is asked at most once, aimed at the weakest signal after the two standard answers.
  // "answers" are stand-ins: the simulator uses them as voice transcripts and the presenter can paste them.
  sets: [
    {
      questions: {
        implementation: { label: 'How it works', text: 'In your own words, how does your code implement “{title}”? Walk us through the core logic.' },
        rationale: { label: 'Why this way', text: 'Why did you implement the core logic this way? What did you consider instead?' }
      },
      probes: {
        specific: { label: 'Be concrete', text: 'Give one concrete input and say exactly what your code returns for it, and why.' },
        reasoning: { label: 'The other way', text: 'What would have gone wrong if you had chosen the other approach?' }
      },
      answers: {
        specific: {
          implementation: 'I added a calculate_fee function in fees.py. It takes the transfer amount, multiplies it by 1 percent, then clamps the result between a 2.00 minimum and a 25.00 cap. The total charged is the amount plus that fee, rounded to two decimals at the end. I used Decimal so a $50 transfer costs exactly 2.00, not 0.50.',
          rationale: 'I chose to clamp instead of using a tiered table because it is one rule the finance team can read in a line. I considered tiers, but every new tier would need another test. Rounding once at the end avoids the cents drifting when the fee is computed twice.',
          probe: 'For $50 the 1 percent is 0.50, so the 2.00 minimum applies and the total is 52.00. For $5,000 the fee would be 50, so the 25.00 cap applies and the total is 5,025.00.'
        },
        generic: {
          implementation: 'The code implements the fee calculation in a clean and robust way. It follows best practices and handles the transfer amount properly to make sure the correct fee is applied.',
          rationale: 'I used this approach because it is a standard and scalable solution. Overall it improves maintainability and leverages the existing utilities in the codebase.',
          probe: 'It works correctly in all cases as expected and follows the standard approach.'
        }
      }
    },
    {
      questions: {
        implementation: { label: 'How it works', text: 'Pick one transfer and follow it through your code. What happens at each step until the final charge is worked out?' },
        rationale: { label: 'Why this way', text: 'Which part of this change was the hardest decision, and why did you settle on that choice?' }
      },
      probes: {
        specific: { label: 'Be concrete', text: 'Name one amount where the minimum applies and one where the cap applies, and give the total for each.' },
        reasoning: { label: 'If it changed', text: 'If the fee rule changed next month, what would you have to touch, and why?' }
      },
      answers: {
        specific: {
          implementation: 'Take a $200 transfer. My calculate_fee function takes 1 percent, which is 2.00, and that is exactly the minimum, so the fee stays 2.00. The total charged is then 202.00. With $5,000 the percent would be 50.00, so the clamp holds it at the 25.00 cap. I used Decimal and rounded once at the end.',
          rationale: 'The hardest decision was where to round. I first rounded the fee and the total separately, but the cents drifted, so I chose to round once at the end because it avoids that drift. I considered floats instead of Decimal, but 0.1 plus 0.2 gives 0.30000000000000004 in a float, so I kept Decimal.',
          probe: '$50 gives 0.50, so the 2.00 minimum applies and the total is 52.00. $5,000 would give 50.00, so the 25.00 cap applies and the total is 5,025.00.'
        },
        generic: {
          implementation: 'The function calculates the fee in a clean and robust way. It takes the transfer and returns the correct total, and it handles the different cases properly as expected.',
          rationale: 'It was the most efficient and maintainable choice. Overall it is a well-structured and scalable solution that follows best practices.',
          probe: 'It works correctly and follows the standard approach in every case.'
        }
      }
    }
  ],

  // The scoring standard. A senior-reviewed check adds Risk x Novelty x Gap points to the portfolio (1 to 27).
  // Risk and Novelty are fixed for this pull request; Gap follows the person's level on the concept (see sim.js).
  scoring: {
    max: 27,
    concept: { name: 'Fees and rounding', start: 1 },
    r: 3,
    n: 1,
    why: { r: 'Money flow: this change charges a fee.', n: 'You changed fees.py in an earlier pull request.' },
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

  // Illustration for the portfolio trend: dashed, labelled SYNTHETIC, never stored and never counted in any score.
  syntheticHistory: [41, 38, 45, 44, 50, 49, 55, 58, 57, 63, 66, 64, 71, 75]
};
