FROM node:22-trixie


COPY . /workspace


RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*



WORKDIR /workspace/examples/sandbox/aiwaf-fastify-proxy

RUN npm install

EXPOSE 3002

RUN npx aiwaf manifest --framework fastify --output .aiwaf/paths.json

CMD ["npm", "start"]
