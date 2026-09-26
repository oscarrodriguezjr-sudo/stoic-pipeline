# For Render's cron job service (or any container host).
#
# IMPORTANT: this does NOT fetch fonts — it relies on `COPY . .` picking up
# the same assets/fonts/*.ttf files you already downloaded and verified
# locally with `python -m pipeline.run --check`. Make sure those two files
# are actually committed to this repo (check they're not caught by a
# .gitignore font-ignoring rule) before deploying — don't try to re-fetch
# them from a guessed URL at build time; the exact filename Google Fonts
# ships has changed conventions before, and getting it wrong here means a
# build that "succeeds" but silently ships without the real fonts.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -c "from pathlib import Path; import sys; \
  a=Path('assets/fonts/Cinzel[wght].ttf').exists(); \
  b=Path('assets/fonts/CormorantGaramond-Italic[wght].ttf').exists(); \
  sys.exit(0) if (a and b) else (print('Missing font file(s) in the build context — see the note above this line in the Dockerfile') or sys.exit(1))"

# no CMD/ENTRYPOINT — render.yaml's startCommand picks the channel per service
