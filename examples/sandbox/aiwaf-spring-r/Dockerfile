FROM maven:3.9.8-eclipse-temurin-17@sha256:d62e34e458c64b13e7a38ec055264082b4235a1ea2c3b3d881ad04d6ca20311e AS build
COPY --from=aiwaf_source /java /opt/aiwaf-java
RUN --mount=type=cache,id=aiwaf-maven,target=/root/.m2,sharing=locked mvn -q -f /opt/aiwaf-java/pom.xml -DskipTests -Dgpg.skip=true install
WORKDIR /workspace

COPY examples/sandbox/aiwaf-spring /workspace/examples/sandbox/aiwaf-spring
WORKDIR /workspace/examples/sandbox/aiwaf-spring
RUN --mount=type=cache,id=aiwaf-maven,target=/root/.m2,sharing=locked mvn -q -DskipTests package

FROM rocker/r-ver:4.6.1@sha256:4e6e6696ff54a86625c7f80046478e67014a2184e942b85eeff43db7b992d93e
RUN apt-get update && apt-get install -y default-jre openssl=3.0.13-0ubuntu3.16 libssl3t64=3.0.13-0ubuntu3.16 && \
    Rscript -e "install.packages('jsonlite', repos='https://cloud.r-project.org')" && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /workspace/examples/sandbox/aiwaf-spring/target/aiwaf-spring-example-0.1.0.jar /app/app.jar

ENV PORT=8083
ENV TARGET_BASE_URL=http://juice:3000
ENV AIWAF_BACKEND=fastr
EXPOSE 8083
CMD ["java", "-jar", "/app/app.jar"]
LABEL io.github.aiwaf.source="https://github.com/aayushgauba/aiwaf.git#843a35f4fd48b4ef565e3c1ec8a42db9b1c41946"
