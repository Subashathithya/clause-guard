import json
import pathlib
import urllib.request

AUTH = pathlib.Path.home() / "AppData/Roaming/xdg.data/com.vercel.cli/auth.json"
token = json.loads(AUTH.read_text(encoding="utf-8"))["token"]
HEADERS = {"Authorization": f"Bearer {token}", "User-Agent": "clauseguard"}


def api(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        "https://api.vercel.com" + path,
        data=data,
        headers={**HEADERS, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:600]
    except Exception as exc:
        return None, str(exc)[:200]


PROJECT = "prj_9YWhco0S0fkk9eGy4hUcC5qJHsaJ"

status, team = api("GET", "/v2/teams")
teams = team.get("teams") or []
print("teams ->", status)
for t in teams:
    print(
        f"  {t.get('id')} | {t.get('name')} | oidc={json.dumps(t.get('oidcTokenConfig'))[:160]} | "
        f"ssoRedirect={json.dumps(t.get('ssoRedirect'))[:120]}"
    )

status, project = api("GET", "/v9/projects/" + PROJECT)
team_id = project.get("accountId") or (project.get("link") or {}).get("organizationId")
print("project team id:", team_id)

print()
print("--- attempt 1: project-level opt-out ---")
st, res = api(
    "PATCH",
    "/v9/projects/" + PROJECT,
    {"oidcTokenConfig": {"enabled": False, "issuerMode": "team"}},
)
print("PATCH project ->", st, json.dumps(res)[:200] if isinstance(res, dict) else str(res)[:200])

if team_id:
    print()
    print("--- attempt 2: team-level ---")
    st, res = api(
        "PATCH",
        "/v2/teams/" + team_id,
        {"oidcTokenConfig": {"enabled": False}},
    )
    print("PATCH team ->", st, json.dumps(res)[:300] if isinstance(res, dict) else str(res)[:300])

print()
st, project = api("GET", "/v9/projects/" + PROJECT)
print("after: project.oidcTokenConfig =", json.dumps(project.get("oidcTokenConfig")))
