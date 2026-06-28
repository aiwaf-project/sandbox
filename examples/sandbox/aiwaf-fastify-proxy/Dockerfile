FROM node:22-trixie


COPY . /workspace


RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*



WORKDIR /workspace/examples/sandbox/aiwaf-fastify-proxy

RUN npm install
RUN mkdir -p node_modules/aiwaf-js/node_modules && ln -sf ../../aiwaf-wasm node_modules/aiwaf-js/node_modules/aiwaf-wasm

EXPOSE 3002

RUN npx aiwaf manifest --framework fastify --output .aiwaf/paths.json

CMD ["npm", "start"]
