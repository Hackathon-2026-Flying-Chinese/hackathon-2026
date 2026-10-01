/* What every page may know: the company, the person, the reviewer and the other checks on the commit.
   Everything here is synthetic: the company, the code, the customers and the invoices. */
window.Viva = window.Viva || {};
Viva.data = {
  // The company the demo runs in (a made-up payments company), and the person using it. The avatar file is assets/avatar.jpg.
  org: { name: 'Harbourpay', team: 'Billing Engineering' },
  me: { name: 'Tony', role: 'Graduate engineer', avatar: 'assets/avatar.jpg' },
  // The senior assigned to review this team's checks. A demo identity: the reviewer page is opened by a token, not SSO.
  reviewer: { name: 'Priya Raman', role: 'Senior engineer, Billing' },
  // Other checks on the same commit, shown in the GitHub preview. They all pass: the tests only ever ask as one customer.
  ci: [{ name: 'ci / unit-tests', note: 'Passed in 1m 04s' }, { name: 'ci / lint', note: 'Passed in 16s' }],
  // The pull request, its tasks (code, the three checks with their answers, the rubric, stand-in answers), the scoring
  // standard and the interview limits live in data/tasks.json. With the server, only the server reads it; the pages get
  // the question side of the task and the limits in the session view.

  // Illustration for the portfolio trend: dashed, labelled SYNTHETIC, never stored and never counted in any score.
  syntheticHistory: [41, 38, 45, 44, 50, 49, 55, 58, 57, 63, 66, 64, 71, 75]
};
