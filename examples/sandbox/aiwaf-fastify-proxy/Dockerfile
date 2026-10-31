FROM node:22-trixie@sha256:def2655045ff1ee91b28a48cb3ec84feafef6d128bda0ff6903e7847ed0b27b4 AS build
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY examples/sandbox/aiwaf-fastify-proxy/package*.json /workspace/examples/sandbox/aiwaf-fastify-proxy/
WORKDIR /workspace/examples/sandbox/aiwaf-fastify-proxy
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev
COPY examples/sandbox/aiwaf-fastify-proxy /workspace/examples/sandbox/aiwaf-fastify-proxy
COPY examples/sandbox/common /workspace/examples/sandbox/common
EXPOSE 3002
RUN npx aiwaf manifest --framework fastify --output .aiwaf/paths.json


FROM node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa
# Runtime has no npm/npx/Yarn; application dependencies are installed in the build stage.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* /usr/local/lib/node_modules/npm /opt/yarn-* && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY --from=build /workspace /workspace
WORKDIR /workspace/examples/sandbox/aiwaf-fastify-proxy
EXPOSE 3002
RUN groupadd --gid 10001 aiwaf && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp aiwaf && \
    mkdir -p /logs/aiwaf-fastify-proxy /state && \
    rm -rf logs && ln -s /logs/aiwaf-fastify-proxy logs && \
    ln -s /state/native aiwaf_native_data && chown -R 10001:10001 /logs /state
ENV HOME=/tmp NEXT_TELEMETRY_DISABLED=1
USER 10001:10001
CMD ["node", "server.js"]
LABEL io.github.aiwaf.distribution="npm"
