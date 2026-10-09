FROM node:22-trixie@sha256:def2655045ff1ee91b28a48cb3ec84feafef6d128bda0ff6903e7847ed0b27b4 AS build
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/aiwaf-js
COPY --from=aiwaf_source /js /opt/aiwaf-js
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev
COPY examples/sandbox/aiwaf-nest-proxy/package*.json /workspace/examples/sandbox/aiwaf-nest-proxy/
WORKDIR /workspace/examples/sandbox/aiwaf-nest-proxy
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev
COPY examples/sandbox/aiwaf-nest-proxy /workspace/examples/sandbox/aiwaf-nest-proxy
COPY examples/sandbox/common /workspace/examples/sandbox/common
EXPOSE 3005
RUN npx aiwaf manifest --framework nest --output .aiwaf/paths.json


FROM node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa
RUN npm install --global npm@12.2.0 && npm install --prefix /tmp/npm-security-patches --ignore-scripts --no-audit --no-fund undici@6.28.1 brace-expansion@5.0.11 && cp -a /tmp/npm-security-patches/node_modules/. /usr/local/lib/node_modules/npm/node_modules/ && rm -rf /tmp/npm-security-patches && npm cache clean --force
COPY --from=build /opt/aiwaf-js /opt/aiwaf-js
COPY --from=build /workspace /workspace
WORKDIR /workspace/examples/sandbox/aiwaf-nest-proxy
EXPOSE 3005
CMD ["npm", "start"]
LABEL io.github.aiwaf.source="https://github.com/aayushgauba/aiwaf.git#843a35f4fd48b4ef565e3c1ec8a42db9b1c41946"
