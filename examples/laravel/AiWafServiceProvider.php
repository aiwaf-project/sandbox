<?php

declare(strict_types=1);

namespace App\Providers;

use AIWAF\AIWAF;
use AIWAF\Adapters\InMemoryAdapter;
use AIWAF\RateLimiter;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\ServiceProvider;

class AiWafServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        AIWAF::setPathExistsResolver(static function (string $path): bool {
            $candidate = '/' . ltrim((string) strtok($path, '?'), '/');

            foreach (Route::getRoutes() as $route) {
                $uri = '/' . ltrim($route->uri(), '/');
                if ($candidate === $uri || strpos($candidate, $uri . '/') === 0) {
                    return true;
                }
            }

            return false;
        });

        RateLimiter::initAdapter(new InMemoryAdapter());
        AIWAF::protect();
    }
}
