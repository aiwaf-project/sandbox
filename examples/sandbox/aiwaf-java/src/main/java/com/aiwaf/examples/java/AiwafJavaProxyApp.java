package com.aiwaf.examples.java;

import com.aiwaf.core.AiwafConfig;
import com.aiwaf.core.AiwafDecision;
import com.aiwaf.core.AiwafEngine;
import com.aiwaf.core.AiwafRequest;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class AiwafJavaProxyApp {
    private static final Set<String> HOP_BY_HOP_HEADERS = Set.of(
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"
    );

    private final String targetBaseUrl;
    private final AiwafEngine engine;
    private final HttpClient client;

    private AiwafJavaProxyApp(String targetBaseUrl, AiwafEngine engine) {
        this.targetBaseUrl = targetBaseUrl;
        this.engine = engine;
        this.client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(env("PORT", "8080"));
        String target = env("TARGET_BASE_URL", "http://localhost:3000");

        AiwafConfig config = new AiwafConfig();
        config.geoBlockEnabled = false;
        config.rateLimitEnabled = true;
        config.rateLimitWindowSeconds = 10;
        config.rateLimitMax = 20;
        config.rateLimitFloodThreshold = 40;
        config.honeypotEnabled = true;
        config.uuidTamperEnabled = true;
        config.ipKeywordBlockEnabled = true;

        AiwafJavaProxyApp app = new AiwafJavaProxyApp(target, new AiwafEngine(config));

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/", app::handle);
        server.start();
        System.out.println("aiwaf-java proxy listening on :" + port + " forwarding to " + target);
    }

    private void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        String method = exchange.getRequestMethod();
        Map<String, String> headers = flattenHeaders(exchange);
        String ip = clientIp(exchange, headers);
        String country = headers.getOrDefault("x-country-code", "US");

        AiwafDecision decision = engine.evaluate(new AiwafRequest(
                method,
                path,
                ip,
                country,
                headers,
                queryMap(exchange.getRequestURI().getRawQuery()),
                System.currentTimeMillis(),
                Set.of()
        ));

        if (!decision.allowed()) {
            byte[] body = ("{\"blocked\":true,\"reason\":\"" + jsonEscape(decision.reason()) + "\"}")
                    .getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("content-type", "application/json");
            exchange.sendResponseHeaders(decision.statusCode(), body.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(body);
            }
            return;
        }

        byte[] requestBody = readAll(exchange.getRequestBody());
        HttpRequest.Builder forward = HttpRequest.newBuilder()
                .uri(upstreamUri(exchange.getRequestURI()))
                .timeout(Duration.ofSeconds(20));

        if ("GET".equalsIgnoreCase(method) || "HEAD".equalsIgnoreCase(method)) {
            forward.method(method, HttpRequest.BodyPublishers.noBody());
        } else {
            forward.method(method, requestBody.length == 0
                    ? HttpRequest.BodyPublishers.noBody()
                    : HttpRequest.BodyPublishers.ofByteArray(requestBody));
        }

        exchange.getRequestHeaders().forEach((name, values) -> {
            String lower = name.toLowerCase(Locale.ROOT);
            if (HOP_BY_HOP_HEADERS.contains(lower)) {
                return;
            }
            for (String value : values) {
                forward.header(name, value);
            }
        });

        try {
            HttpResponse<byte[]> upstream = client.send(forward.build(), HttpResponse.BodyHandlers.ofByteArray());
            exchange.getResponseHeaders().clear();
            upstream.headers().map().forEach((name, values) -> {
                String lower = name.toLowerCase(Locale.ROOT);
                if (HOP_BY_HOP_HEADERS.contains(lower)) {
                    return;
                }
                exchange.getResponseHeaders().put(name, new ArrayList<>(values));
            });
            byte[] responseBody = upstream.body() == null ? new byte[0] : upstream.body();
            exchange.sendResponseHeaders(upstream.statusCode(), responseBody.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(responseBody);
            }
        } catch (Exception ex) {
            byte[] body = ("{\"error\":\"upstream_failure\",\"message\":\"" + jsonEscape(ex.getMessage()) + "\"}")
                    .getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("content-type", "application/json");
            exchange.sendResponseHeaders(502, body.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(body);
            }
        }
    }

    private URI upstreamUri(URI incoming) {
        StringBuilder sb = new StringBuilder(targetBaseUrl);
        sb.append(incoming.getRawPath() == null ? "/" : incoming.getRawPath());
        if (incoming.getRawQuery() != null && !incoming.getRawQuery().isBlank()) {
            sb.append('?').append(incoming.getRawQuery());
        }
        return URI.create(sb.toString());
    }

    private static Map<String, String> flattenHeaders(HttpExchange exchange) {
        Map<String, String> out = new HashMap<>();
        exchange.getRequestHeaders().forEach((k, v) -> out.put(k.toLowerCase(Locale.ROOT), String.join(",", v)));
        return out;
    }

    private static String clientIp(HttpExchange exchange, Map<String, String> headers) {
        String forwarded = headers.get("x-forwarded-for");
        if (forwarded != null && !forwarded.isBlank()) {
            int comma = forwarded.indexOf(',');
            return (comma >= 0 ? forwarded.substring(0, comma) : forwarded).trim();
        }
        return exchange.getRemoteAddress().getAddress().getHostAddress();
    }

    private static Map<String, String> queryMap(String rawQuery) {
        Map<String, String> out = new HashMap<>();
        if (rawQuery == null || rawQuery.isBlank()) {
            return out;
        }
        String[] pairs = rawQuery.split("&");
        for (String pair : pairs) {
            if (pair.isBlank()) {
                continue;
            }
            int idx = pair.indexOf('=');
            if (idx < 0) {
                out.put(pair, "");
            } else {
                out.put(pair.substring(0, idx), pair.substring(idx + 1));
            }
        }
        return out;
    }

    private static byte[] readAll(InputStream in) throws IOException {
        return in.readAllBytes();
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String jsonEscape(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
