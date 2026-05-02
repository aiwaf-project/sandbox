<?php

declare(strict_types=1);

namespace App\Security;

use AIWAF\AIWAF;
use AIWAF\Adapters\InMemoryAdapter;
use AIWAF\RateLimiter;
use Symfony\Component\Routing\RouterInterface;

final class AiWafBootstrap
{
    public static function protect(RouterInterface $router): void
    {
        AIWAF::setPathExistsResolver(static function (string $path) use ($router): bool {
            $candidate = '/' . ltrim((string) strtok($path, '?'), '/');

            foreach ($router->getRouteCollection() as $route) {
                $routePath = (string) $route->getPath();
                if ($routePath !== '' && ($candidate === $routePath || strpos($candidate, rtrim($routePath, '/') . '/') === 0)) {
                    return true;
                }
            }

            return false;
        });

        RateLimiter::initAdapter(new InMemoryAdapter());
        AIWAF::protect();
    }
}
