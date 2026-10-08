FROM maven:3.9.8-eclipse-temurin-17 AS build
WORKDIR /workspace

COPY examples/sandbox/aiwaf-java /workspace/examples/sandbox/aiwaf-java
WORKDIR /workspace/examples/sandbox/aiwaf-java
RUN mvn -q -DskipTests package

FROM rocker/r-ver:4.6.1
RUN apt-get update && apt-get install -y default-jre && \
    Rscript -e "install.packages('jsonlite', repos='https://cloud.r-project.org')" && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY examples/sandbox/aiwaf-java/aiwaf.json /app/aiwaf.json
COPY --from=build /workspace/examples/sandbox/aiwaf-java/target/aiwaf-java-example-0.1.0.jar /app/app.jar

ENV PORT=8082
ENV TARGET_BASE_URL=http://juice:3000
ENV AIWAF_BACKEND=fastr
EXPOSE 8082
CMD ["java", "-jar", "/app/app.jar"]
