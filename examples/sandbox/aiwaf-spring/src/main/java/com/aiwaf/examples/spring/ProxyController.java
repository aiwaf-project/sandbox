package com.aiwaf.examples.spring;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@RestController
public class ProxyController {
    private static final Set<String> HOP_BY_HOP_HEADERS = Set.of(
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"
    );

    private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .version(HttpClient.Version.HTTP_1_1)
            .build();

    @Value("${aiwaf.target-base-url:http://localhost:3000}")
    private String targetBaseUrl;

    @RequestMapping("/**")
    public ResponseEntity<byte[]> proxy(HttpServletRequest request, @RequestBody(required = false) byte[] body) {
        String rawPath = request.getRequestURI();
        String rawQuery = request.getQueryString();
        String target = targetBaseUrl + rawPath + (rawQuery == null || rawQuery.isBlank() ? "" : "?" + rawQuery);

        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(target))
                .timeout(Duration.ofSeconds(20));

        copyRequestHeaders(request, builder);

        byte[] payload = body == null ? new byte[0] : body;
        String method = request.getMethod();
        if ("GET".equalsIgnoreCase(method) || "HEAD".equalsIgnoreCase(method)) {
            builder.method(method, HttpRequest.BodyPublishers.noBody());
        } else {
            builder.method(method, payload.length == 0
                    ? HttpRequest.BodyPublishers.noBody()
                    : HttpRequest.BodyPublishers.ofByteArray(payload));
        }

        try {
            HttpResponse<byte[]> response = client.send(builder.build(), HttpResponse.BodyHandlers.ofByteArray());
            HttpHeaders headers = new HttpHeaders();
            response.headers().map().forEach((name, values) -> {
                String lower = name.toLowerCase(Locale.ROOT);
                if (!HOP_BY_HOP_HEADERS.contains(lower)) {
                    headers.put(name, new ArrayList<>(values));
                }
            });
            return ResponseEntity.status(response.statusCode()).headers(headers).body(response.body());
        } catch (Exception ex) {
            String msg = ex.getMessage() == null ? "" : ex.getMessage();
            byte[] bodyBytes = ("{\"error\":\"upstream_failure\",\"message\":\""
                    + msg.replace("\\", "\\\\").replace("\"", "\\\"") + "\"}")
                    .getBytes(StandardCharsets.UTF_8);
            return ResponseEntity.status(502).body(bodyBytes);
        }
    }

    private static void copyRequestHeaders(HttpServletRequest request, HttpRequest.Builder builder) {
        Enumeration<String> names = request.getHeaderNames();
        while (names.hasMoreElements()) {
            String name = names.nextElement();
            String lower = name.toLowerCase(Locale.ROOT);
            if (HOP_BY_HOP_HEADERS.contains(lower)) {
                continue;
            }
            Enumeration<String> values = request.getHeaders(name);
            while (values.hasMoreElements()) {
                builder.header(name, values.nextElement());
            }
        }
    }
}
