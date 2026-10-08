FROM node:22-trixie

COPY . /workspace

RUN apt-get update && apt-get install -y python3 make g++ \
  && rm -rf /var/lib/apt/lists/*


WORKDIR /workspace/examples/sandbox/aiwaf-hapi-proxy

RUN npm_config_build_from_source=true npm install

EXPOSE 3003
RUN npx aiwaf manifest --framework hapi --output .aiwaf/paths.json
CMD ["npm", "start"]
