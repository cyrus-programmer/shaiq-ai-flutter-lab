const input = $input.first().json;
return [{
  json: {
    accepted: false,
    error: 'invalid_ticket',
    details: input.errors,
    received_at: input.received_at
  }
}];
