# Deployment mit Docker

Diese Datei beschreibt, wie Lineguard auf dem eigenen Server unter `https://lineguard.dlsystem.de` läuft. Auf dem Server laufen schon `nginx-proxy` und `acme-companion`. Lineguard hängt sich an diese beiden an.

## Aufbau

`docker-compose.yml` startet zwei Container:

| Container | Inhalt | Port im Container |
|---|---|---|
| `api` | Backend mit API und Agenten (`python -m lineguard run`) | 8000 |
| `web` | Die Seite (Next.js) | 3000 |

`nginx-proxy` ist der Reverse Proxy (Vermittler zwischen Browser und Containern). Er liest die Variablen `VIRTUAL_HOST`, `VIRTUAL_PATH` und `VIRTUAL_PORT` der beiden Container. Er leitet `/api/...` ohne das `/api` an `api` (`VIRTUAL_DEST: /`) und alles andere an `web`. `acme-companion` liest `LETSENCRYPT_HOST` und holt das Zertifikat von Let's Encrypt. Seite und API laufen so auf derselben Adresse, und CORS spielt keine Rolle.

Zwei Ordner auf dem Server kommen als Volume (Ordner, den der Container vom Server liest) in den Container `api`:

- `packs/`: das Kundenpaket, zum Beispiel `packs/soony_gh6/`. Es ist nicht im Repository.
- `data/`: Datenbank, gelesene Dateien und Mails. Dieser Ordner bleibt bei einem Neustart erhalten.

## Voraussetzungen

1. Der DNS-Eintrag `lineguard.dlsystem.de` zeigt auf den Server.
2. Die Container `nginx-proxy` und `nginx-proxy-acme` laufen.
3. Du kennst das Docker-Netz von `nginx-proxy`. Zeige es so an:

   ```bash
   docker inspect nginx-proxy --format '{{json .NetworkSettings.Networks}}'
   ```

   Wenn der Name nicht `nginx-proxy` ist, trage ihn in `.env` als `PROXY_NETWORK=<name>` ein.

## Erster Start

1. Hole das Repository auf den Server:

   ```bash
   cd ~/docker && git clone <repo-url> lineguard && cd lineguard
   ```

2. Kopiere das Kundenpaket nach `packs/soony_gh6/`. Es kommt von einem Rechner des Teams, nicht aus Git.
3. Lege die Datei `.env` an und trage die Werte ein:

   ```bash
   cp .env.example .env
   ```

   Wichtig sind `XAI_API_KEY`, `PORTAL_TOKEN`, `GMAIL_APP_PASSWORD`, `MAIL_MODE` und gegebenenfalls `PROXY_NETWORK`. Lass `MAIL_MODE=DRY_RUN`, bis ihr Mails wirklich senden wollt.
4. Baue und starte die Container:

   ```bash
   docker compose up -d --build
   ```

5. Lies alle Dateien des Kunden einmal ein. Ohne diesen Schritt liest der Watcher sie nach und nach selbst:

   ```bash
   docker compose exec api python -m lineguard import
   ```

6. Warte etwa eine Minute auf das Zertifikat. Öffne dann `https://lineguard.dlsystem.de`. Prüfe die API unter `https://lineguard.dlsystem.de/api/healthz`.

## Einstellungen in `.env`

Docker Compose liest `.env` an zwei Stellen. Der Container `api` bekommt alle Werte. Compose selbst liest diese Werte für `docker-compose.yml`:

| Variable | Standard | Zweck |
|---|---|---|
| `LINEGUARD_DOMAIN` | `lineguard.dlsystem.de` | Adresse für `nginx-proxy` und das Zertifikat |
| `LINEGUARD_PACK` | `packs/soony_gh6` | Ordner des Kundenpakets im Container |
| `PROXY_NETWORK` | `nginx-proxy` | Docker-Netz des Containers `nginx-proxy` |

Ein Wert in `.env` darf kein `$` enthalten, sonst liest Compose ihn falsch. Schreibe ein `$` als `$$`.

## Zugang schützen

Die Seite ist öffentlich. Jeder, der die Adresse kennt, kann eine Person wählen und freigeben. Bei `MAIL_MODE=LIVE` gehen dann echte Mails an Lieferanten. Schütze die Seite darum mit einem Passwort. `nginx-proxy` liest dafür eine Datei mit dem Namen der Domain aus `/etc/nginx/htpasswd/`:

1. Finde den Ordner auf dem Server, der in `nginx-proxy` als `/etc/nginx/htpasswd` eingebunden ist:

   ```bash
   docker inspect nginx-proxy --format '{{json .Mounts}}'
   ```

2. Wenn es diesen Ordner nicht gibt, musst du ihn in der Compose-Datei von `nginx-proxy` als Volume ergänzen und `nginx-proxy` neu starten.
3. Lege in diesem Ordner die Datei `lineguard.dlsystem.de` an (`htpasswd` kommt aus dem Paket `apache2-utils`):

   ```bash
   htpasswd -c <ordner>/lineguard.dlsystem.de team
   ```

4. Starte `nginx-proxy` neu, damit er die Datei liest:

   ```bash
   docker restart nginx-proxy
   ```

## Betrieb

| Aufgabe | Befehl |
|---|---|
| Logs des Backends lesen | `docker compose logs -f api` |
| Neue Version holen und starten | `git pull && docker compose up -d --build` |
| Zustand neu berechnen | `docker compose exec api python -m lineguard recompute` |
| Demo-Zustand zurücksetzen | `docker compose exec api python -m lineguard demo-reset` |
| Alles stoppen | `docker compose down` |

`docker compose down` löscht keine Daten. Datenbank und Dateien liegen in `data/` auf dem Server.

Die Adresse der API steckt beim Bauen in der Seite (`NEXT_PUBLIC_API_BASE=/api`). Wenn du sie änderst, baue `web` neu.
