FROM maven:3.9.8-eclipse-temurin-17@sha256:d62e34e458c64b13e7a38ec055264082b4235a1ea2c3b3d881ad04d6ca20311e AS build
COPY --from=aiwaf_source /java /opt/aiwaf-java
RUN --mount=type=cache,id=aiwaf-maven,target=/root/.m2,sharing=locked mvn -q -f /opt/aiwaf-java/pom.xml -DskipTests -Dgpg.skip=true install
WORKDIR /workspace

COPY examples/sandbox/aiwaf-java /workspace/examples/sandbox/aiwaf-java
WORKDIR /workspace/examples/sandbox/aiwaf-java
RUN --mount=type=cache,id=aiwaf-maven,target=/root/.m2,sharing=locked mvn -q -DskipTests package

FROM eclipse-temurin:17-jre@sha256:207ecae0b2b104dfc6dfa763d1e9cd2041cb344800a180e24cb1a28ed533ff90
WORKDIR /app
COPY examples/sandbox/aiwaf-java/aiwaf.json /app/aiwaf.json
COPY --from=build /workspace/examples/sandbox/aiwaf-java/target/aiwaf-java-example-0.1.0.jar /app/app.jar

ENV PORT=8080
ENV TARGET_BASE_URL=http://juice:3000
EXPOSE 8080
CMD ["java", "-jar", "/app/app.jar"]
LABEL io.github.aiwaf.source="https://github.com/aayushgauba/aiwaf.git#843a35f4fd48b4ef565e3c1ec8a42db9b1c41946"
