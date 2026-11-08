import { createHmac, timingSafeEqual } from 'node:crypto';
import { Readable } from 'node:stream';

const MAX_BYTES = 8192, SKEW_SECONDS = 300, MAX_REPLAYS = 10000;
const seen = new Map();
const required = ['event_id', 'source', 'check', 'severity', 'status', 'at', 'summary'];
const sources = ['acme-validate', 'acme-renew', 'edge', 'openplans', 'signoz', 'watchdog'];
const severities = ['info', 'warning', 'critical', 'recovery'];
const statuses = ['ok', 'fail', 'unknown'];
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

function isoTime(value) {
  if (typeof value !== 'string') return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|([+-])(\d{2}):(\d{2}))$/.exec(value);
  if (!match) return false;
  const [, year, month, day, hour, minute, second, , offsetHour = 0, offsetMinute = 0] = match;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1] &&
    hour <= 23 && minute <= 59 && second <= 59 && offsetHour <= 23 && offsetMinute <= 59 &&
    Number.isFinite(Date.parse(value));
}

function valid(event) {
  return object(event) && required.every(key => Object.hasOwn(event, key)) &&
    Object.keys(event).every(key => required.includes(key) || key === 'details') &&
    typeof event.event_id === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(event.event_id) &&
    sources.includes(event.source) && typeof event.check === 'string' && /^[a-z0-9][a-z0-9._-]{0,63}$/i.test(event.check) &&
    severities.includes(event.severity) && statuses.includes(event.status) && isoTime(event.at) &&
    typeof event.summary === 'string' && [...event.summary].length <= 280 &&
    (!Object.hasOwn(event, 'details') || (object(event.details) && Object.keys(event.details).length <= 20 &&
      Object.values(event.details).every(value => typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value)))));
}

export async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'method_not_allowed' });
  }
  const secret = process.env.OPENHRA_ALERT_SECRET;
  if (!secret) return res.status(503).json({ error: 'not_configured' });
  if (Number(req.headers['content-length']) > MAX_BYTES) return res.status(413).json({ error: 'body_too_large' });

  const timestamp = req.headers['x-openhra-timestamp'], signature = req.headers['x-openhra-signature'];
  const now = Math.floor(Date.now() / 1000);
  if (typeof timestamp !== 'string' || !/^\d{1,12}$/.test(timestamp) || Math.abs(now - Number(timestamp)) > SKEW_SECONDS ||
      typeof signature !== 'string' || !/^sha256=[0-9a-f]{64}$/i.test(signature)) {
    return res.status(401).json({ error: 'unauthorized' });
  }

  const chunks = [];
  let size = 0;
  try {
    // Keep the socket open on overflow so the 413 response can reach the sender.
    for await (const chunk of req.iterator({ destroyOnReturn: false })) {
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      size += bytes.length;
      if (size > MAX_BYTES) {
        req.resume();
        return res.status(413).json({ error: 'body_too_large' });
      }
      chunks.push(bytes);
    }
  } catch {
    return res.status(400).json({ error: 'invalid_body' });
  }
  const body = Buffer.concat(chunks);
  const expected = createHmac('sha256', secret).update(timestamp + '.').update(body).digest();
  if (!timingSafeEqual(expected, Buffer.from(signature.slice(7), 'hex'))) return res.status(401).json({ error: 'unauthorized' });

  let event;
  try {
    event = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(body));
  } catch {
    return res.status(400).json({ error: 'invalid_json' });
  }
  if (!valid(event)) return res.status(400).json({ error: 'invalid_event' });

  for (const [id, expires] of seen) if (expires < now) seen.delete(id);
  const id = event.event_id.toLowerCase();
  if (seen.has(id)) return res.status(409).json({ error: 'replayed_event' });
  if (seen.size >= MAX_REPLAYS) seen.delete(seen.keys().next().value);
  seen.set(id, Math.max(now, Number(timestamp)) + SKEW_SECONDS);

  const line = JSON.stringify({ ...event, received_at: new Date().toISOString() });
  if (event.severity === 'critical') console.error(line);
  else if (event.severity === 'warning') console.warn(line);
  else console.log(line);
  return res.status(204).end();
}

// The fetch entry point bypasses Vercel's Node helpers and automatic body reader.
export default {
  async fetch(request) {
    const req = request.body ? Readable.fromWeb(request.body) : Readable.from([]);
    req.method = request.method;
    req.headers = Object.fromEntries(request.headers);
    const headers = new Headers();
    const res = {
      statusCode: 200,
      setHeader(key, value) { headers.set(key, value); },
      status(code) { this.statusCode = code; return this; },
      json(value) {
        headers.set('Content-Type', 'application/json');
        return new Response(JSON.stringify(value), { status: this.statusCode, headers });
      },
      end() { return new Response(null, { status: this.statusCode, headers }); },
    };
    return handler(req, res);
  },
};
