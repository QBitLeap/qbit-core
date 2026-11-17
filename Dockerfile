# Standalone Qbit runtime component; no website, indexer, data or credentials.
FROM debian:bookworm-20261104-slim@sha256:c67e92c8099ba22853ab4cfda7cfb494d253d6012ca82dee98ba8976772af018 AS unpack
COPY release/qbit-1.0.1-x86_64-linux-gnu.tar.gz /release/qbit.tar.gz
RUN printf '%s\n' '5f3ce43c3525328f4f0cdcc898516e274a16e170e4ed91ccf648bbb1094f6cb6  /release/qbit.tar.gz' | sha256sum --check - \
    && mkdir -p /opt/qbit \
    && tar -xzf /release/qbit.tar.gz -C /opt/qbit --strip-components=1 \
       qbit-1.0.1/bin/qbitd qbit-1.0.1/bin/qbit-cli \
    && printf '%s\n' \
       'c52f801024a48bd1bb19804c065840cf93ab799dfc0b1af4644faef1be3fcd0a  /opt/qbit/bin/qbitd' \
       '6b7ad86f87ca017274f7a10a6998f5c4b36d9c23545b2baddfe16c682708494b  /opt/qbit/bin/qbit-cli' | sha256sum --check - \
    && chmod 0555 /opt/qbit/bin/qbitd /opt/qbit/bin/qbit-cli

FROM debian:bookworm-20261104-slim@sha256:c67e92c8099ba22853ab4cfda7cfb494d253d6012ca82dee98ba8976772af018
COPY --from=unpack /opt/qbit /opt/qbit
COPY COPYING.qbit /usr/share/doc/qbit/COPYING
COPY runtime.lock.json /usr/share/doc/qbit/runtime.lock.json
RUN mkdir -p /data && chown 1000:1000 /data
ENV HOME=/data
LABEL org.opencontainers.image.title="Qbit Core runtime component" \
      org.opencontainers.image.version="1.0.1"
USER 1000:1000
WORKDIR /data
STOPSIGNAL SIGTERM
ENTRYPOINT ["/opt/qbit/bin/qbitd"]
CMD ["--version"]
