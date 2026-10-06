export const meta = {
  name: 'viva-eval-judge',
  description: 'Independent senior-engineer judgement of each generated pack: are the keys right, is it a fair check, was the automatic gate right',
  phases: [{ title: 'Judge', detail: 'one Opus agent per PR, high effort' }],
}

const BACK = '/path/to/repo/backend'  // set to your checkout
const SCRATCH = '/tmp/viva-judge'  // where judges may write scratch scripts
const SET = {
  type: 'object',
  properties: {
    set: { type: 'integer' },
    behaviour_key_correct: { type: 'boolean' }, requirement_key_correct: { type: 'boolean' }, evidence_key_correct: { type: 'boolean' },
    key_notes: { type: 'string', description: 'how you checked each key (read the code, ran it), and what is wrong if anything' },
    question_quality: { type: 'integer', enum: [1, 2, 3, 4, 5] },
    ambiguous: { type: 'boolean', description: 'a careful engineer could defend a different behaviour option' },
    leak: { type: 'boolean', description: 'what the learner reads before locking the predictions gives a prediction answer away' },
    leak_note: { type: 'string' },
  },
  required: ['set', 'behaviour_key_correct', 'requirement_key_correct', 'evidence_key_correct', 'key_notes', 'question_quality', 'ambiguous', 'leak', 'leak_note'],
}
const SCHEMA = {
  type: 'object',
  properties: {
    grounding: { type: 'integer', enum: [1, 2, 3, 4, 5], description: "5 = set 1 is exactly where this PR made its riskiest decision" },
    grounding_note: { type: 'string' },
    concept_fits: { type: 'boolean' },
    sets: { type: 'array', items: SET },
    transfer: { type: 'integer', enum: [1, 2, 3, 4, 5], description: '5 = set 2 tests the same concept on genuinely different code' },
    rubric_quality: { type: 'integer', enum: [1, 2, 3, 4, 5] },
    fair_and_useful: { type: 'integer', enum: [1, 2, 3, 4, 5], description: "would a senior at a small company call this a fair, useful check of the author's understanding" },
    would_ship: { type: 'boolean', description: 'show this pack to the PR author as it is' },
    gate_call: { type: 'string', enum: ['right', 'too_strict', 'too_loose'], description: "the automatic status vs your would_ship: ready+ship or not-ready+no-ship = right; ready but should not ship = too_loose; not ready but fine to ship = too_strict" },
    flaws: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['grounding', 'grounding_note', 'concept_fits', 'sets', 'transfer', 'rubric_quality', 'fair_and_useful', 'would_ship', 'gate_call', 'flaws', 'summary'],
}

phase('Judge')
const out = await parallel(args.map(({ round, slug }) => () => agent(
  `You are a senior engineer judging a product's automatically generated "understanding check" for a real pull request, for an evaluation. Be rigorous and sceptical: the point is to find out whether the generator can be trusted.

The product: the PR author reads code from their PR, locks three predictions per set (behaviour: what a given input returns; requirement: does the code meet the stated rule (yes/no); evidence: which listed test tries the behaviour scenario itself, the same actor, input and data condition, or "none"; every listed test is an option), then answers a short viva graded against a 3-point rubric. Set 2 is a retake on the same concept with different code, used only after a failed first attempt. Before locking the predictions the learner sees only: task.code, task.file and task.fn, task.tests (ids and notes), task.rule, and the three questions with their options. After locking, the viva questions and probes come one at a time (they cannot change locked predictions, but a giveaway there weakens the viva). Everything else (correct ids, facts, reveal, leak, rubric, harness) stays hidden until the results. A set whose task.origin is "variant" is shown with a label saying Viva wrote it for the retake and it is not code from the pull request (its tests are hypothetical too).

Read these files (Read tool; you may also run small Python scripts with Bash to check behaviour, writing scratch files only under ${SCRATCH}/${round}/${slug}/; no network, no git, no other repository files):
- ${BACK}/eval/cache/${slug}/pr.json: the PR title, description, author, and "contents" = whole text at the head commit of changed source files
- ${BACK}/eval/cache/${slug}/diff.patch: the PR's diff
- ${BACK}/eval/runs/${round}/${slug}/result.json: "status" (the automatic gate: ready = shown to learners; needs_review / failed / skipped = not shown), "report" (issues found by code checks, sandbox "runs" with the observed option, blind "solve" answers vs the key, "reasons"), and "pack" (sets[i].task.code/tests/rule/items{behaviour,requirement,evidence: q, options, correct}/facts/reveal/leak, questions, probes, rubric). If pack is null, there is nothing to judge: say so in summary, set would_ship false.

For each set, verify each key yourself from the code (do not trust the facts field): trace the behaviour scenario through the code; for Python you may re-run the harness logic or your own minimal reproduction. Then fill the schema. Write every field in English. would_ship means you would show this exact pack to the author as a fair check with correct keys.`,
  { label: `judge:${round}:${slug}`, phase: 'Judge', schema: SCHEMA, effort: 'high' })
    .then(v => ({ round, slug, verdict: v }))))
return out.filter(Boolean)
