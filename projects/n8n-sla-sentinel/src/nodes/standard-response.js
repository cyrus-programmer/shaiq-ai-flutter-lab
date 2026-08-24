const triage = $input.first().json;
return [{ json: { ...triage, action: 'queue_for_support' } }];
