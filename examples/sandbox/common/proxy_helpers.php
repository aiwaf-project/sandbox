<?php

declare(strict_types=1);

function aiwaf_forward_to_target(string $targetBase): void
{
    $requestUri = (string) ($_SERVER['REQUEST_URI'] ?? '/');
    $targetUrl = rtrim($targetBase, '/') . $requestUri;
    $method = (string) ($_SERVER['REQUEST_METHOD'] ?? 'GET');

    $incomingHeaders = function_exists('getallheaders') ? (array) getallheaders() : [];
    $forwardHeaders = [];
    foreach ($incomingHeaders as $name => $value) {
        $lower = strtolower((string) $name);
        if ($lower === 'host' || $lower === 'content-length' || $lower === 'connection') {
            continue;
        }
        $forwardHeaders[] = $name . ': ' . $value;
    }

    $body = file_get_contents('php://input');
    if ($body === false) {
        $body = '';
    }

    $context = stream_context_create([
        'http' => [
            'method' => $method,
            'header' => implode("\r\n", $forwardHeaders),
            'content' => $body,
            'ignore_errors' => true,
        ],
    ]);

    $response = @file_get_contents($targetUrl, false, $context);
    $responseHeaders = isset($http_response_header) && is_array($http_response_header)
        ? $http_response_header
        : [];

    $status = 200;
    if (isset($responseHeaders[0]) && preg_match('/\s(\d{3})\s/', $responseHeaders[0], $matches) === 1) {
        $status = (int) $matches[1];
    }
    http_response_code($status);

    foreach ($responseHeaders as $line) {
        if (strpos($line, ':') === false) {
            continue;
        }
        [$headerName] = explode(':', $line, 2);
        $nameLower = strtolower(trim($headerName));
        if ($nameLower === 'transfer-encoding' || $nameLower === 'connection') {
            continue;
        }
        header($line, false);
    }

    echo $response !== false ? $response : '';
}
