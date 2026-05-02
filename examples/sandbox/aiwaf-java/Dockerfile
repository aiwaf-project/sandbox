FROM maven:3.9.8-eclipse-temurin-17 AS build
WORKDIR /workspace

COPY examples/sandbox/aiwaf-java /workspace/examples/sandbox/aiwaf-java
WORKDIR /workspace/examples/sandbox/aiwaf-java
RUN mvn -q -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /workspace/examples/sandbox/aiwaf-java/target/aiwaf-java-example-0.1.0.jar /app/app.jar

ENV PORT=8080
ENV TARGET_BASE_URL=http://juice:3000
EXPOSE 8080
CMD ["java", "-jar", "/app/app.jar"]
