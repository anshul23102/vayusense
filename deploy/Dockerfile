FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user: if a future dependency vulnerability or bug ever
# lets an attacker execute code inside this container, they land as an
# unprivileged user, not root -- a real container-escape or arbitrary-write
# bug is far less dangerous from here.
RUN useradd --create-home --shell /usr/sbin/nologin vayusense \
    && chown -R vayusense:vayusense /srv
USER vayusense

ENV PORT=8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
