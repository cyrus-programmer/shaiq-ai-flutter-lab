const { lead, qualification } = $json;
const safeEmail = lead.email.replace(/^(.{1,2}).*(@.*)$/, '$1***$2');
return [{ json: {
  ok: qualification.route !== 'rejected',
  route: qualification.route,
  score: qualification.score,
  owner: qualification.owner,
  lead: { company: lead.company, email: safeEmail, source: lead.source },
  reasons: qualification.reasons,
} }];
