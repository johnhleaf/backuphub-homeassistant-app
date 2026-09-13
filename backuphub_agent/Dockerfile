FROM ghcr.io/home-assistant/base:3.22

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3

COPY run.sh /run.sh
COPY agent.py /agent.py
RUN chmod 0755 /run.sh /agent.py

CMD ["/run.sh"]
