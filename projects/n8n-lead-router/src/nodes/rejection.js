const body = $json.accepted === false
  ? { ok: false, route: 'invalid', errors: $json.errors }
  : { ok: false, route: 'rejected', reason: $json.lead.consent ? 'outside current qualification policy' : 'consent required' };
return [{ json: body }];
