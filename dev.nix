# ═══════════════════════════════════════════════════════════════
#  Transight — IDX / Nix Development Environment
# ═══════════════════════════════════════════════════════════════
# Enables PostgreSQL on port 5432 (database: transight_db),
# Python 3.11, Node 20, and ffmpeg.
# Open ports: 3000 (React dev server), 5000 (Flask API).
# ═══════════════════════════════════════════════════════════════
{ pkgs, ... }: {
  channel = "stable-23.11";

  # ── System Packages ───────────────────────────────────────────
  packages = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.nodejs_20
    pkgs.ffmpeg
  ];

  # ── PostgreSQL Service ────────────────────────────────────────
  services.postgres = {
    enable = true;
    package = pkgs.postgresql_15;
    initialDatabases = [{ name = "transight_db"; }];
    port = 5432;
  };

  # ── Environment Variables ─────────────────────────────────────
  env = {
    DATABASE_URL = "postgresql://user:@localhost:5432/transight_db";
  };

  idx = {
    # ── Workspace lifecycle hooks ─────────────────────────────
    workspace = {
      onCreate = {
        install-python-deps = ''
          cd server && pip install -r requirements.txt
        '';
        install-node-deps = ''
          cd client && npm install
        '';
        seed-database = ''
          cd server && python seed.py
        '';
      };
      onStart = {
        start-flask = ''
          cd server && python app.py &
        '';
        start-react = ''
          cd client && npm run dev &
        '';
      };
    };

    # ── Exposed Ports ─────────────────────────────────────────
    previews = {
      enable = true;
      previews = {
        web = {
          command = [ "npm" "run" "dev" "--" "--port" "$PORT" ];
          cwd = "client";
          manager = "web";
          env = { PORT = "$PORT"; };
        };
      };
    };
  };
}
