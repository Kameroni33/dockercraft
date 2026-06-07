# Slim Minecraft server runtime. The manager provisions /data (jar, mods,
# configs) on the host and bind-mounts it — this image is just a JRE + launcher.
#
# Build per Java major (MC versions require different ones; piston-meta says which):
#   docker build --build-arg JAVA_VERSION=21 -t dockercraft/minecraft:java21 .
ARG JAVA_VERSION=21
FROM eclipse-temurin:${JAVA_VERSION}-jre

# uid 1000 to match the typical host user owning the bind-mounted /data dir.
# The base image ships an `ubuntu` user already holding uid 1000 — replace it.
RUN userdel -r ubuntu 2>/dev/null; useradd --uid 1000 --create-home minecraft
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER minecraft
WORKDIR /data
EXPOSE 25565/tcp 25565/udp 25575/tcp

ENTRYPOINT ["/entrypoint.sh"]
