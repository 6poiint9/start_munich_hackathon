# Secure Coding: JavaScript, TypeScript, Node.js

Rules that add to the general ones in `SKILL.md`. Based on the OWASP Node.js,
DOM-based XSS, and Prototype Pollution cheat sheets.

## Code execution

- Never pass untrusted data to `eval`, `new Function`, `setTimeout`/
  `setInterval` with a string, `vm` (it is not a sandbox), or dynamic
  `import()`/`require()` paths.
- Run processes with `execFile`/`spawn` and an argument array, `shell: false`
  (the default). `exec` and `shell: true` go through a shell and allow
  injection.
- Avoid template engines' unescaped output (`<%-`, `{{{ }}}`, `| safe`) for
  untrusted data.

## Prototype pollution and objects

- When merging, cloning, or setting properties by user-controlled keys, reject
  `__proto__`, `constructor`, and `prototype`, or use `Map` /
  `Object.create(null)` for dictionaries.
- Validate parsed JSON with a schema (zod, ajv, valibot) before use; type
  assertions (`as T`) check nothing at runtime.
- Use `Object.hasOwn(obj, key)` instead of `key in obj` for lookups on
  untrusted keys.

## Browser and DOM

- Write untrusted text with `textContent`, `setAttribute` on safe attributes,
  or framework bindings (`{value}` in React/Vue/Angular). Avoid `innerHTML`,
  `outerHTML`, `insertAdjacentHTML`, `document.write`,
  `dangerouslySetInnerHTML`, `v-html`, and `bypassSecurityTrust*`; if HTML is
  required, sanitize it with DOMPurify.
- Allow only `https:` (and `mailto:` where needed) for user-supplied URLs in
  `href`/`src`; `javascript:` URLs execute code.
- Set a Content Security Policy without `unsafe-inline` and `unsafe-eval`;
  use nonces or hashes for needed inline scripts. Add `rel="noopener
  noreferrer"` to `target="_blank"` links.
- Check `event.origin` against an allowlist in every `message` listener, and
  pass an explicit target origin to `postMessage`, never `"*"` with sensitive
  data.
- Keep tokens out of `localStorage`/`sessionStorage` (readable by any XSS);
  prefer `HttpOnly; Secure; SameSite=Lax` (or `Strict`) cookies.

## Node.js servers

- Use `helmet` (or equivalent headers), CORS with an explicit origin
  allowlist and no `*` with credentials, and CSRF protection for
  cookie-authenticated state-changing routes.
- Limit request body size and rate-limit authentication and expensive
  endpoints.
- Use parameterized queries or the ORM's bound parameters; never interpolate
  into SQL template strings (Prisma `$queryRawUnsafe`, Sequelize `literal`,
  Knex `raw` with concatenation).
- Join paths with `path.resolve(base, input)` and confirm the result starts
  with `base + path.sep`; reject input containing null bytes.
- Avoid regular expressions with nested quantifiers on untrusted input
  (ReDoS); bound input length or use `re2`.
- Verify JWTs with an explicit algorithm allowlist (`algorithms: ['RS256']`),
  issuer, audience, and expiry; never accept `alg: none`.
- Hash passwords with `argon2` or `bcrypt`; generate tokens with
  `crypto.randomBytes`/`crypto.randomUUID`, never `Math.random`; compare with
  `crypto.timingSafeEqual`.
- Keep `NODE_ENV=production` in production so frameworks hide stack traces.

## Dependencies and build

- Check npm packages with the `checking-npm-packages` skill before installing.
- Treat every build-time env var prefixed for the client (`NEXT_PUBLIC_`,
  `VITE_`, `REACT_APP_`) as public.
- Do not ship source maps with secrets or internal paths to public hosts
  unless intended.
