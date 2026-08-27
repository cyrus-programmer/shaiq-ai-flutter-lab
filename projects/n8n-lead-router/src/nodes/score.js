const { lead, signals, policy } = $json;
const reasons = [];
let score = 0;

const add = (points, reason) => { score += points; reasons.push({ points, reason }); };
if (signals.businessEmail) add(15, 'business email');
if (signals.targetIndustry) add(20, 'target industry');
if (signals.targetCountry) add(10, 'target country');
if (lead.employeeCount >= 20 && lead.employeeCount <= 2000) add(20, 'target company size');
else if (lead.employeeCount > 2000) add(10, 'enterprise company size');
if (lead.annualBudget >= 25000) add(25, 'budget at or above 25000');
else if (lead.annualBudget >= 10000) add(15, 'budget at or above 10000');
else if (lead.annualBudget >= 5000) add(5, 'budget at or above 5000');
if (lead.painPoint.length >= 80) add(10, 'detailed pain point');

score = Math.min(score, 100);
const route = !lead.consent ? 'rejected' : score >= 70 ? 'sales' : score >= 40 ? 'nurture' : 'rejected';
const ownerIndex = [...lead.company.toLowerCase()].reduce((sum, char) => sum + char.charCodeAt(0), 0)
  % policy.owners.length;

return [{ json: {
  ...$json,
  qualification: {
    score,
    route,
    reasons,
    owner: route === 'sales' ? policy.owners[ownerIndex] : null,
  },
} }];
