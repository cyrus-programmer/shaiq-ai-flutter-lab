const source = $input.first().json;
const body = source.body && typeof source.body === 'object' ? source.body : source;
const text = (value) => typeof value === 'string' ? value.trim() : '';
const ticketId = text(body.ticket_id);
const subject = text(body.subject);
const message = text(body.message);
const email = text(body.customer_email).toLowerCase();
const tier = text(body.customer_tier).toLowerCase() || 'standard';
const channel = text(body.channel).toLowerCase() || 'webhook';
const affectedUsers = Number(body.affected_users ?? 0);
const errors = [];

if (ticketId.length < 1 || ticketId.length > 100) errors.push('ticket_id must be 1 to 100 characters');
if (subject.length < 3 || subject.length > 200) errors.push('subject must be 3 to 200 characters');
if (message.length < 10 || message.length > 5000) errors.push('message must be 10 to 5000 characters');
if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.push('customer_email must be valid');
if (!Number.isInteger(affectedUsers) || affectedUsers < 0 || affectedUsers > 1000000) {
  errors.push('affected_users must be an integer from 0 to 1000000');
}
if (!['standard', 'premium', 'enterprise'].includes(tier)) {
  errors.push('customer_tier must be standard, premium, or enterprise');
}

const occurredAt = text(body.occurred_at);
if (occurredAt && Number.isNaN(Date.parse(occurredAt))) errors.push('occurred_at must be an ISO-8601 date');

return [{
  json: {
    valid: errors.length === 0,
    errors,
    received_at: new Date().toISOString(),
    ticket: {
      id: ticketId,
      subject,
      message,
      customer_email: email || null,
      customer_tier: tier,
      affected_users: Number.isFinite(affectedUsers) ? affectedUsers : 0,
      channel,
      occurred_at: occurredAt || null
    }
  }
}];
