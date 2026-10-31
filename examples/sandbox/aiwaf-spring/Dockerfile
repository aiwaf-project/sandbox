FROM maven:3.9.8-eclipse-temurin-17@sha256:d62e34e458c64b13e7a38ec055264082b4235a1ea2c3b3d881ad04d6ca20311e AS build
WORKDIR /workspace

COPY examples/sandbox/aiwaf-spring /workspace/examples/sandbox/aiwaf-spring
WORKDIR /workspace/examples/sandbox/aiwaf-spring
RUN --mount=type=cache,id=aiwaf-maven,target=/root/.m2,sharing=locked mvn -q -DskipTests package

FROM eclipse-temurin:17-jre-noble@sha256:900322f4cc1b9da9d730ae4bb56d8a1dabbaa9cfa32809fc8b542b600370a045
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* && rm -f /usr/bin/pebble
WORKDIR /app
COPY --from=build /workspace/examples/sandbox/aiwaf-spring/target/aiwaf-spring-example-0.1.0.jar /app/app.jar

ENV PORT=8081
ENV TARGET_BASE_URL=http://juice:3000
EXPOSE 8081
RUN groupadd --gid 10001 aiwaf && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp aiwaf && \
    mkdir -p /logs/aiwaf-spring /state && ln -s /logs/aiwaf-spring /app/aiwaf_logs && chown -R 10001:10001 /logs /state
ENV HOME=/tmp
USER 10001:10001
CMD ["java", "-jar", "/app/app.jar"]
LABEL io.github.aiwaf.distribution="maven-central"
