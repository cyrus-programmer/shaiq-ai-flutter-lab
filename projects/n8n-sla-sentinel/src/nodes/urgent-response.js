const triage = $input.first().json;
return [{ json: { ...triage, action: 'page_on_call' } }];
