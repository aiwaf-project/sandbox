FROM node:22-trixie

COPY . /workspace

RUN apt-get update && apt-get install -y python3 make g++ \
  && rm -rf /var/lib/apt/lists/*


WORKDIR /workspace/examples/sandbox/aiwaf-adonis-proxy

RUN npm_config_build_from_source=true npm install
RUN mkdir -p node_modules/aiwaf-js/node_modules && ln -sf ../../aiwaf-wasm node_modules/aiwaf-js/node_modules/aiwaf-wasm

EXPOSE 3007
RUN npx aiwaf manifest --framework next --output .aiwaf/paths.json || echo '{"routes":{}}' > .aiwaf/paths.json
CMD ["npm", "start"]
