# Production on a single VPS

These are the exact files that run **https://basirapp.site** (Ubuntu 24.04 · Docker Compose · Caddy 2).
The server follows `main` of this repository: a systemd timer checks GitHub every 60 s and, when a new
commit appears, rebuilds and restarts the stack, then health-checks it. A failed build leaves the running
site untouched (Compose replaces the container only after a successful build).

| File | Installed as | Role |
|---|---|---|
| `docker-compose.prod.yml` | `/opt/basira/docker-compose.prod.yml` | Overlay on `docker-compose.yml`: no public app port, CORS for the site, trusted proxy range, Caddy service |
| `Caddyfile.example` | `/opt/basira/Caddyfile` | Automatic HTTPS, `www` → apex, basic auth on writes to `/v1/models/config` |
| `autodeploy.sh` | `/opt/basira/autodeploy.sh` | Compare server commit with `$BRANCH` of `$REPO`; fetch, rebuild, health-check, log |
| `autodeploy.conf.example` | `/opt/basira/autodeploy.conf` | `REPO`, `BRANCH` to follow, `COMPOSE_PROFILES` (`bot` = Telegram bot) |
| `deploy.sh` | `/opt/basira/deploy.sh` | Manual forced redeploy |
| `basira-autodeploy.service` / `.timer` | `/etc/systemd/system/` | Run `autodeploy.sh` every 60 s |
| `basira-deploy.logrotate` | `/etc/logrotate.d/basira-deploy` | Weekly rotation of `/var/log/basira-deploy.log` |

## Install (once)

```bash
git clone https://github.com/MoTechSys/Project-Basira.git /opt/basira && cd /opt/basira
cp deploy/vps/{docker-compose.prod.yml,autodeploy.sh,deploy.sh} . && chmod +x autodeploy.sh deploy.sh
cp deploy/vps/autodeploy.conf.example autodeploy.conf
cp deploy/vps/Caddyfile.example Caddyfile
# replace <BCRYPT_HASH> with the output of:
docker run --rm caddy:2-alpine caddy hash-password --plaintext '<admin password>'
cp deploy/vps/basira-autodeploy.{service,timer} /etc/systemd/system/
cp deploy/vps/basira-deploy.logrotate /etc/logrotate.d/basira-deploy
systemctl daemon-reload && systemctl enable --now basira-autodeploy.timer
./deploy.sh
```

Then follow `docs/DEPLOYMENT.md` §3 (model key in `/settings`, the three live checks).

## Operate

```bash
tail -20 /var/log/basira-deploy.log                 # deploy history (commit, duration, health)
systemctl list-timers basira-autodeploy.timer       # next check
/opt/basira/deploy.sh                               # force a redeploy now
curl -s https://basirapp.site/health                # build_sha = deployed commit
```

**Rollback:** `git -C /opt/basira reset --hard <sha> && BUILD_SHA=<sha> docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`,
and set `BRANCH` to a branch pinned at that commit (or stop the timer) so the next check does not move it forward.

Secrets (admin password, model key, bot token) never live in this repository: the hash is only in the server's
`Caddyfile`, the model key is stored by the app in the `/data` volume, and the bot token / eval key live in
`/etc/basira/*.env` (600 root).

## Telegram bot (profile `bot`)

```bash
install -d -m 700 /etc/basira
key=$(openssl rand -hex 24)
printf 'BASIRA_EVAL_KEY=%s\n' "$key"                                   > /etc/basira/basira.env
printf 'TELEGRAM_BOT_TOKEN=%s\nBASIRA_EVAL_KEY=%s\n' '<token>' "$key" > /etc/basira/telegram-bot.env
chmod 600 /etc/basira/*.env
sed -i 's/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=bot/' /opt/basira/autodeploy.conf
/opt/basira/deploy.sh                                   # or wait for the next commit on main
```

`autodeploy.sh` exports `COMPOSE_PROFILES` before `docker compose up`, and after a successful deploy appends
`bot: healthy|unhealthy|missing` (from `docker inspect`) to the log. Without the profile the stack is the site
only — `docker compose up` in a fresh clone is unchanged for judges. Details and the verification list:
`docs/DEPLOYMENT.md` §3.1.
