FROM node:22-trixie

COPY . /workspace

RUN apt-get update && apt-get install -y python3 make g++ \
  && rm -rf /var/lib/apt/lists/*


WORKDIR /workspace/examples/sandbox/aiwaf-koa-proxy

RUN npm_config_build_from_source=true npm install

EXPOSE 3004
RUN npx aiwaf manifest --framework koa --output .aiwaf/paths.json
CMD ["npm", "start"]
