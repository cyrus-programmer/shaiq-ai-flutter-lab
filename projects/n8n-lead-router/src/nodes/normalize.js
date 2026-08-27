const input = $json.body ?? $json;
const text = (value, max = 200) => String(value ?? '').trim().slice(0, max);
const list = (name, fallback) => text($env[name] || fallback, 1000)
  .split(',').map((value) => value.trim().toLowerCase()).filter(Boolean);

const email = text(input.email, 254).toLowerCase();
const company = text(input.company, 160);
const website = text(input.website, 300).toLowerCase().replace(/\/$/, '');
const employeeCount = Number.parseInt(input.employeeCount, 10);
const annualBudget = Number.parseFloat(input.annualBudget);
const submittedAt = text(input.submittedAt, 40);
const source = text(input.source || 'unknown', 60).toLowerCase();
const painPoint = text(input.painPoint, 1200);
const consent = input.consent === true;

const errors = [];
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.push('email must be valid');
if (company.length < 2) errors.push('company must contain at least 2 characters');
if (!Number.isFinite(employeeCount) || employeeCount < 1 || employeeCount > 10000000) {
  errors.push('employeeCount must be an integer between 1 and 10000000');
}
if (!Number.isFinite(annualBudget) || annualBudget < 0 || annualBudget > 1000000000) {
  errors.push('annualBudget must be between 0 and 1000000000');
}
if (!submittedAt || Number.isNaN(Date.parse(submittedAt))) errors.push('submittedAt must be ISO-8601');
if (painPoint.length < 20) errors.push('painPoint must contain at least 20 characters');

const domain = email.includes('@') ? email.split('@').at(-1) : '';
const freeDomains = new Set(['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']);
const country = text(input.country, 2).toLowerCase();
const industry = text(input.industry, 80).toLowerCase();
const targetIndustries = list('TARGET_INDUSTRIES', 'healthcare,saas,fintech,ecommerce');
const targetCountries = list('TARGET_COUNTRIES', 'us,ca,gb,de,au');
const owners = list('SALES_OWNERS', 'sales@example.com');

return [{ json: {
  accepted: errors.length === 0,
  errors,
  lead: {
    email, company, website, employeeCount, annualBudget, submittedAt,
    source, painPoint, consent, country: country.toUpperCase(), industry,
  },
  policy: { targetIndustries, targetCountries, owners },
  signals: {
    businessEmail: Boolean(domain) && !freeDomains.has(domain),
    targetIndustry: targetIndustries.includes(industry),
    targetCountry: targetCountries.includes(country),
  },
} }];
