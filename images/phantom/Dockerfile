# phantom (github.com/jhead/phantom): makes a Bedrock server appear as a "LAN
# game" so consoles (Switch/Xbox/PS) can discover it. Runs host-networked —
# Bedrock LAN discovery is a UDP broadcast to 19132, which never traverses
# Docker's bridge NAT, so a published port can't receive it.
#
# Upstream ships no checksums; PHANTOM_SHA256 is a self-computed pin of the
# release asset (curl ... | sha256sum) — recompute and update on version bump.
#
#   docker build -t dockercraft/phantom:latest .
ARG PHANTOM_VERSION=0.5.4
FROM alpine:3.20
ARG PHANTOM_VERSION
ARG PHANTOM_SHA256=8677271ac0b2b19b7ea8b526331ddca6bf5e95a91eac3dd8588b7871e810b1ed

RUN wget -q -O /usr/local/bin/phantom \
      "https://github.com/jhead/phantom/releases/download/v${PHANTOM_VERSION}/phantom-linux" \
 && echo "${PHANTOM_SHA256}  /usr/local/bin/phantom" | sha256sum -c - \
 && chmod +x /usr/local/bin/phantom \
    # usage output mentions -server; proves the binary executes on this base
 && (/usr/local/bin/phantom -h 2>&1 || true) | grep -q server

USER nobody
ENTRYPOINT ["/usr/local/bin/phantom"]
