from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compose_keeps_backend_private_and_tunnel_optional() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    backend_block = compose.split("  backend:", 1)[1].split("  nginx:", 1)[0]
    tunnel_block = compose.split("  cloudflared:", 1)[1].split("networks:", 1)[0]

    assert "ports:" not in backend_block
    assert "--workers\"" not in backend_block
    assert 'profiles: ["tunnel"]' in tunnel_block
    assert "TUNNEL_TOKEN" in tunnel_block
    assert "cloudflare/cloudflared:latest" not in compose


def test_nginx_forwards_cloudflare_https_and_supports_long_jobs() -> None:
    nginx = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert "proxy_pass http://vnptcto_backend;" in nginx
    assert "proxy_set_header X-Forwarded-Proto https;" in nginx
    assert "proxy_set_header Upgrade $http_upgrade;" in nginx
    assert "proxy_read_timeout 1800s;" in nginx
    assert "location = /nginx-health" in nginx


def test_server_example_contains_no_real_secret() -> None:
    env_example = (ROOT / ".env.server.example").read_text(encoding="utf-8")

    required_empty_values = (
        "SESSION_SECRET=",
        "SUPABASE_SECRET_KEY=",
        "CLOUDFLARE_TUNNEL_TOKEN=",
        "OTP_ENCRYPTION_KEY=",
        "MOBILE_GATEWAY_MASTER_KEY=",
    )
    for expected in required_empty_values:
        assert expected in env_example

    assert "APP_DATABASE_BACKEND=supabase" in env_example
    assert "APP_PUBLIC_URL=https://vnptcto.com" in env_example

