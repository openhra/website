// Returns the contact address only after a server-side reCAPTCHA check.
// CONTACT_EMAIL, RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY live in Vercel env vars, never in git.
export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') {
    const siteKey = process.env.RECAPTCHA_SITE_KEY;
    return res.status(siteKey ? 200 : 503).json(siteKey ? { siteKey } : { error: 'not_configured' });
  }
  if (req.method !== 'POST') return res.status(405).json({ error: 'method_not_allowed' });
  const secret = process.env.RECAPTCHA_SECRET_KEY, email = process.env.CONTACT_EMAIL;
  if (!secret || !email) return res.status(503).json({ error: 'not_configured' });
  const token = typeof req.body?.token === 'string' ? req.body.token : '';
  if (!token || token.length > 4096) return res.status(400).json({ error: 'missing_token' });
  try {
    const check = await fetch('https://www.google.com/recaptcha/api/siteverify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ secret, response: token }),
      signal: AbortSignal.timeout(5000),
    });
    const result = await check.json();
    if (!result.success) return res.status(403).json({ error: 'captcha_failed' });
    return res.status(200).json({ email });
  } catch {
    return res.status(502).json({ error: 'captcha_unavailable' });
  }
}
