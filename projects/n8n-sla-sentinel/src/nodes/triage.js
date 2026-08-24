const input = $input.first().json;
const ticket = input.ticket;
const combined = `${ticket.subject} ${ticket.message}`.toLowerCase();
let score = 0;
const reasons = [];

const addOnce = (pattern, points, reason) => {
  if (pattern.test(combined)) {
    score += points;
    reasons.push(reason);
  }
};

addOnce(/\b(outage|down|unavailable|offline|production broken)\b/, 45, 'service outage');
addOnce(/\b(security|breach|hacked|compromised|ransomware|data leak)\b/, 50, 'security impact');
addOnce(/\b(payment|checkout|billing|charged|transaction)\b/, 25, 'payment impact');
addOnce(/\b(data loss|deleted|corrupt|missing data)\b/, 40, 'data integrity impact');
addOnce(/\b(urgent|immediately|critical|emergency)\b/, 15, 'urgent language');
addOnce(/\b(blocked|cannot work|can't work|stopped working)\b/, 15, 'customer blocked');

if (ticket.customer_tier === 'enterprise') {
  score += 20;
  reasons.push('enterprise customer');
} else if (ticket.customer_tier === 'premium') {
  score += 10;
  reasons.push('premium customer');
}

if (ticket.affected_users >= 100) {
  score += 25;
  reasons.push(`${ticket.affected_users} users affected`);
} else if (ticket.affected_users >= 10) {
  score += 15;
  reasons.push(`${ticket.affected_users} users affected`);
} else if (ticket.affected_users > 1) {
  score += 5;
  reasons.push(`${ticket.affected_users} users affected`);
}

score = Math.min(score, 100);
let severity = 'low';
let slaMinutes = 480;
let route = 'support_standard';
if (score >= 75) {
  severity = 'critical';
  slaMinutes = 15;
  route = 'on_call';
} else if (score >= 50) {
  severity = 'high';
  slaMinutes = 60;
  route = 'on_call';
} else if (score >= 25) {
  severity = 'medium';
  slaMinutes = 240;
  route = 'support_priority';
}

const redact = (value) => value
  .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, '[EMAIL_REDACTED]')
  .replace(/\b(?:\d[ -]*?){13,19}\b/g, '[CARD_REDACTED]')
  .replace(/(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)/g, '[PHONE_REDACTED]');
const safePreview = redact(ticket.message).slice(0, 280);
const baseTime = ticket.occurred_at ? new Date(ticket.occurred_at) : new Date(input.received_at);
const acknowledgeBy = new Date(baseTime.getTime() + slaMinutes * 60_000).toISOString();

return [{
  json: {
    accepted: true,
    ticket_id: ticket.id,
    severity,
    score,
    route,
    is_urgent: severity === 'critical' || severity === 'high',
    sla_minutes: slaMinutes,
    acknowledge_by: acknowledgeBy,
    reasons: reasons.length ? reasons : ['no elevated risk signals'],
    safe_preview: safePreview,
    received_at: input.received_at
  }
}];
